"""Web tools for the Browser agent.

All tools are async and HTTP-only (httpx). Tavily is called via its REST API
directly, so no extra SDK dependency is required. Every tool returns a short
human-readable string; failures produce error strings, never exceptions.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from sentinel_core.config import get_secret

logger = logging.getLogger(__name__)

_TIMEOUT = 12.0
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TAVILY_URL = "https://api.tavily.com/search"


async def _tavily(query: str, max_results: int) -> list[dict] | str:
    """Call the Tavily REST search API. Returns result dicts or an error string."""
    api_key = get_secret("TAVILY_API_KEY")
    if not api_key:
        return "Tavily API key is not configured (set TAVILY_API_KEY)."
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _TAVILY_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
    except httpx.TimeoutException:
        return "Web search timed out. Please try again."
    except httpx.HTTPError as exc:
        logger.warning("Tavily search failed: %s", exc)
        return f"Web search failed: {exc}"


def _format_search_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"No search results found for: {query}"
    lines = [f"Search results for '{query}':", ""]
    for i, item in enumerate(results, 1):
        title = item.get("title", "No title")
        url = item.get("url", "")
        content = (item.get("content") or "")[:200]
        lines.append(f"{i}. {title}\n   URL: {url}\n   {content}")
    return "\n".join(lines)


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web with Tavily and return titles, URLs, and summaries.

    Use for general questions, current events, or anything requiring
    up-to-date information from the internet.

    Args:
        query: The search query.
        max_results: Number of results to return (1-10, default 5).
    """
    max_results = max(1, min(10, max_results))
    results = await _tavily(query, max_results)
    if isinstance(results, str):
        return results
    return _format_search_results(query, results)


@tool
async def read_webpage(url: str) -> str:
    """Fetch a webpage and return its title plus readable text content.

    Use when the user wants the content of a specific URL (e.g. to
    summarize an article). Content is truncated to ~2000 characters.

    Args:
        url: Full URL including http:// or https://.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return "Invalid URL. Please include http:// or https://."
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return f"Timeout: the webpage took too long to respond ({url})."
    except httpx.HTTPError as exc:
        logger.warning("read_webpage failed for %s: %s", url, exc)
        return f"Error accessing webpage: {exc}"

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else "No title"

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = ""
        for selector in ("article", "main", ".content", "#content", ".post", ".entry-content"):
            area = soup.select_one(selector)
            if area:
                text = area.get_text(separator="\n", strip=True)
                break
        if not text and soup.body:
            text = soup.body.get_text(separator="\n", strip=True)

        cleaned = "\n".join(line.strip() for line in text.split("\n") if line.strip())
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000] + "... [truncated]"
        return f"{title}\nURL: {url}\n\n{cleaned}"
    except Exception as exc:
        logger.warning("read_webpage parse failed for %s: %s", url, exc)
        return f"Error reading webpage content: {exc}"


@tool
async def get_weather(location: str) -> str:
    """Get the current weather for a location via wttr.in (no API key needed).

    Args:
        location: City or place name, e.g. "London" or "New York".
    """
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            resp = await client.get(f"https://wttr.in/{location}?format=j1")
            resp.raise_for_status()
            data = resp.json()

        current = data["current_condition"][0]
        area = data["nearest_area"][0]
        name = area["areaName"][0]["value"]
        country = area["country"][0]["value"]
        return (
            f"Weather for {name}, {country}:\n"
            f"Temperature: {current['temp_C']}C / {current['temp_F']}F "
            f"(feels like {current['FeelsLikeC']}C)\n"
            f"Conditions: {current['weatherDesc'][0]['value']}\n"
            f"Humidity: {current['humidity']}%\n"
            f"Wind: {current['windspeedKmph']} km/h"
        )
    except httpx.TimeoutException:
        return "Weather service timed out. Please try again."
    except Exception as exc:
        logger.warning("get_weather failed for %s: %s", location, exc)
        return f"Error getting weather for '{location}': {exc}"


@tool
async def get_weather_forecast(location: str, days: int = 3) -> str:
    """Get a multi-day weather forecast for a location via wttr.in.

    Args:
        location: City or place name.
        days: Number of days to forecast (1-3).
    """
    days = max(1, min(3, days))
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            resp = await client.get(f"https://wttr.in/{location}?format=j1")
            resp.raise_for_status()
            data = resp.json()

        area = data["nearest_area"][0]
        name = area["areaName"][0]["value"]
        country = area["country"][0]["value"]
        lines = [f"{days}-day forecast for {name}, {country}:"]
        for day in data["weather"][:days]:
            midday = day["hourly"][4]
            lines.append(
                f"{day['date']}: high {day['maxtempC']}C, low {day['mintempC']}C, "
                f"{midday['weatherDesc'][0]['value']}"
            )
        return "\n".join(lines)
    except httpx.TimeoutException:
        return "Weather service timed out. Please try again."
    except Exception as exc:
        logger.warning("get_weather_forecast failed for %s: %s", location, exc)
        return f"Error getting forecast for '{location}': {exc}"


@tool
async def get_latest_news(topic: str | None = None, max_results: int = 5) -> str:
    """Get the latest news headlines, optionally filtered by topic.

    Args:
        topic: Optional topic, e.g. "technology" or "sports". Omit for
            general headlines.
        max_results: Number of headlines (1-10, default 5).
    """
    max_results = max(1, min(10, max_results))
    query = f"latest news about {topic}" if topic else "latest news headlines today"
    results = await _tavily(query, max_results)
    if isinstance(results, str):
        return results
    return "Latest news:\n\n" + _format_search_results(query, results)


@tool
async def translate_text(text: str, target_language: str = "en") -> str:
    """Translate text to a target language using the MyMemory API.

    Args:
        text: The text to translate.
        target_language: Target language code, e.g. "en", "es", "fr", "ja".
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": f"auto|{target_language}"},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("responseStatus") == 200:
            translated = data["responseData"]["translatedText"]
            detected = data["responseData"].get("detectedLanguage", "auto")
            return f"Translation ({detected} -> {target_language}): {translated}"
        return "Translation failed. Check the language code and try again."
    except httpx.TimeoutException:
        return "Translation service timed out. Please try again."
    except Exception as exc:
        logger.warning("translate_text failed: %s", exc)
        return f"Error translating text: {exc}"


@tool
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies using live exchange rates.

    Args:
        amount: Amount to convert.
        from_currency: Source currency code, e.g. "USD".
        to_currency: Target currency code, e.g. "EUR".
    """
    from_code = from_currency.upper().strip()
    to_code = to_currency.upper().strip()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.frankfurter.app/latest",
                params={"amount": amount, "from": from_code, "to": to_code},
            )
            resp.raise_for_status()
            data = resp.json()

        rates = data.get("rates", {})
        if to_code not in rates:
            return f"Conversion failed. Check the currency codes ({from_code}, {to_code})."
        converted = rates[to_code]
        rate = converted / amount if amount else 0
        return (
            f"{amount} {from_code} = {converted:.2f} {to_code} "
            f"(rate: 1 {from_code} = {rate:.4f} {to_code}, date: {data.get('date', 'N/A')})"
        )
    except httpx.TimeoutException:
        return "Currency service timed out. Please try again."
    except Exception as exc:
        logger.warning("convert_currency failed: %s", exc)
        return f"Error converting currency: {exc}"


@tool
async def get_definition(word: str) -> str:
    """Look up the dictionary definition of an English word.

    Args:
        word: The word to define.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
            if resp.status_code == 404:
                return f"Word '{word}' not found in the dictionary."
            resp.raise_for_status()
            data = resp.json()

        if not data:
            return f"No definition found for '{word}'."
        entry = data[0]
        lines = [f"Definition of '{entry['word']}'"]
        if entry.get("phonetic"):
            lines[0] += f" ({entry['phonetic']})"
        for meaning in entry.get("meanings", [])[:3]:
            first = meaning["definitions"][0]
            lines.append(f"{meaning['partOfSpeech']}: {first['definition']}")
            if first.get("example"):
                lines.append(f"  Example: {first['example']}")
        return "\n".join(lines)
    except httpx.TimeoutException:
        return "Dictionary service timed out. Please try again."
    except Exception as exc:
        logger.warning("get_definition failed for %s: %s", word, exc)
        return f"Error getting definition: {exc}"


@tool
async def check_website_status(url: str) -> str:
    """Check whether a website is online and measure its response time.

    Args:
        url: The website URL (scheme optional; https is assumed).
    """
    if not urlparse(url).scheme:
        url = f"https://{url}"
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
        elapsed_ms = (time.monotonic() - start) * 1000
        return (
            f"{url} is online (HTTP {resp.status_code}), "
            f"response time {elapsed_ms:.0f} ms, {len(resp.content)} bytes."
        )
    except httpx.TimeoutException:
        return f"Timeout: {url} took longer than {_TIMEOUT:.0f} seconds to respond."
    except httpx.ConnectError:
        return f"Connection error: unable to reach {url}. The site may be down."
    except Exception as exc:
        logger.warning("check_website_status failed for %s: %s", url, exc)
        return f"Error checking website: {exc}"


@tool
async def shorten_url(long_url: str) -> str:
    """Shorten a long URL using the TinyURL API.

    Args:
        long_url: The URL to shorten.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get("https://tinyurl.com/api-create.php", params={"url": long_url})
            resp.raise_for_status()
        return f"Shortened URL: {resp.text.strip()}"
    except httpx.TimeoutException:
        return "URL shortener timed out. Please try again."
    except Exception as exc:
        logger.warning("shorten_url failed: %s", exc)
        return f"Error shortening URL: {exc}"


@tool
async def search_wikipedia(query: str, sentences: int = 5) -> str:
    """Look up a topic on Wikipedia and return a short summary.

    Use for factual, encyclopedic questions (people, places, concepts).

    Args:
        query: Topic to look up.
        sentences: Summary length in sentences (1-10, default 5).
    """
    sentences = max(1, min(10, sentences))
    api_url = "https://en.wikipedia.org/w/api.php"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            search_resp = await client.get(
                api_url,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1,
                },
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("query", {}).get("search", [])
            if not hits:
                return f"No Wikipedia article found for: {query}"
            title = hits[0]["title"]

            extract_resp = await client.get(
                api_url,
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "extracts",
                    "exsentences": sentences,
                    "exintro": True,
                    "explaintext": True,
                    "format": "json",
                },
            )
            extract_resp.raise_for_status()
            pages = extract_resp.json().get("query", {}).get("pages", {})
            extract = next(iter(pages.values())).get("extract", "No content available.")

        link = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        return f"Wikipedia: {title}\n\n{extract}\n\nRead more: {link}"
    except httpx.TimeoutException:
        return "Wikipedia timed out. Please try again."
    except Exception as exc:
        logger.warning("search_wikipedia failed for %s: %s", query, exc)
        return f"Error fetching Wikipedia article: {exc}"


@tool
async def get_stock_price(ticker: str) -> str:
    """Get the current stock price and daily change for a ticker symbol.

    Args:
        ticker: Stock ticker symbol, e.g. "AAPL", "TSLA", "MSFT".
    """
    ticker = ticker.upper().strip()
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            resp = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}")
            resp.raise_for_status()
            data = resp.json()

        result = data.get("chart", {}).get("result") or []
        if not result:
            return f"No data found for ticker '{ticker}'. Check the symbol."
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose", meta.get("previousClose"))
        currency = meta.get("currency", "USD")
        name = meta.get("longName") or meta.get("shortName") or ticker

        line = f"{name} ({ticker}): {price} {currency}"
        if isinstance(price, (int, float)) and isinstance(prev, (int, float)) and prev:
            diff = price - prev
            pct = diff / prev * 100
            line += f", change {diff:+.2f} ({pct:+.2f}%), previous close {prev} {currency}"
        return line
    except httpx.TimeoutException:
        return "Stock data service timed out. Please try again."
    except Exception as exc:
        logger.warning("get_stock_price failed for %s: %s", ticker, exc)
        return f"Error fetching stock price for {ticker}: {exc}"


@tool
async def search_reddit(query: str, subreddit: str = "", limit: int = 5) -> str:
    """Search Reddit posts by keyword, optionally within one subreddit.

    Args:
        query: Search query.
        subreddit: Optional subreddit name without the "r/" prefix.
        limit: Number of results (1-10, default 5).
    """
    limit = max(1, min(10, limit))
    base_url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        if subreddit
        else "https://www.reddit.com/search.json"
    )
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "SentinelAI/1.0"}, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(
                base_url,
                params={
                    "q": query,
                    "sort": "relevance",
                    "limit": limit,
                    "restrict_sr": bool(subreddit),
                },
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])

        if not posts:
            return f"No Reddit posts found for: {query}"
        where = f"r/{subreddit}" if subreddit else "Reddit"
        lines = [f"Reddit search for '{query}' on {where}:"]
        for i, wrapper in enumerate(posts, 1):
            p = wrapper.get("data", {})
            lines.append(
                f"{i}. {p.get('title', 'No title')} "
                f"({p.get('subreddit_name_prefixed', '')}, {p.get('score', 0)} points, "
                f"{p.get('num_comments', 0)} comments)\n"
                f"   https://reddit.com{p.get('permalink', '')}"
            )
        return "\n".join(lines)
    except httpx.TimeoutException:
        return "Reddit timed out. Please try again."
    except Exception as exc:
        logger.warning("search_reddit failed for %s: %s", query, exc)
        return f"Error searching Reddit: {exc}"


TOOLS = [
    web_search,
    read_webpage,
    get_weather,
    get_weather_forecast,
    get_latest_news,
    translate_text,
    convert_currency,
    get_definition,
    check_website_status,
    shorten_url,
    search_wikipedia,
    get_stock_price,
    search_reddit,
]
