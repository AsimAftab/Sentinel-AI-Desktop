# src/tools/browser_tools.py
"""
Browser / Web tools — all HTTP-bound tools are async (httpx.AsyncClient).
Tavily (sync SDK) is offloaded to a thread pool via asyncio.to_thread().

LangGraph calls async tools with `await` when the graph is invoked via
`astream()` / `ainvoke()`, keeping the event loop free during network I/O.
"""

import asyncio
import os
import webbrowser
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

# Shared httpx headers to mimic a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Private async helper — Tavily uses a sync SDK so we offload to thread pool
# ---------------------------------------------------------------------------


async def _tavily_search(query: str, max_results: int) -> list:
    """Run Tavily search in a thread pool to avoid blocking the event loop."""

    def _sync():
        tavily = TavilySearchResults(max_results=max_results)
        return tavily.run(query)

    return await asyncio.to_thread(_sync)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def tavily_web_search(query: str, max_results: int = 5) -> str:
    """
    Performs a comprehensive web search using Tavily API.
    Returns detailed search results with summaries and sources.

    Args:
        query: The search query
        max_results: Number of results to return (1-10)
    """
    try:
        max_results = max(1, min(10, max_results))
        results = await _tavily_search(query, max_results)

        if not results:
            return f"No search results found for: {query}"

        formatted = f"🔍 Search Results for: '{query}'\n\n"
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                if isinstance(result, dict):
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    content = result.get("content", "No content available")
                    formatted += f"{i}. **{title}**\n"
                    formatted += f"   URL: {url}\n"
                    formatted += f"   Summary: {content[:200]}...\n\n"
                else:
                    formatted += f"{i}. {str(result)}\n\n"
        else:
            formatted += str(results)

        return formatted
    except Exception as e:
        return f"Error performing web search: {e}"


@tool
async def scrape_webpage(url: str) -> str:
    """
    Scrapes and extracts text content from a webpage.

    Args:
        url: The URL of the webpage to scrape
    """
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return "Invalid URL provided. Please include http:// or https://"

        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        title = soup.find("title")
        title_text = title.get_text().strip() if title else "No title found"

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        main_content = ""
        for selector in ["article", "main", ".content", "#content", ".post", ".entry-content"]:
            area = soup.select_one(selector)
            if area:
                main_content = area.get_text(separator="\n", strip=True)
                break

        if not main_content:
            body = soup.find("body")
            if body:
                main_content = body.get_text(separator="\n", strip=True)

        lines = [l.strip() for l in main_content.split("\n") if l.strip()]
        cleaned = "\n".join(lines)
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000] + "... [Content truncated]"

        return f"📄 **{title_text}**\n🔗 URL: {url}\n\n📝 **Content:**\n{cleaned}"

    except httpx.TimeoutException:
        return f"Timeout error: The webpage took too long to respond — {url}"
    except httpx.RequestError as e:
        return f"Error accessing webpage: {e}"
    except Exception as e:
        return f"Error scraping webpage: {e}"


@tool
def open_webpage_in_browser(url: str) -> str:
    """
    Opens a webpage in the default system browser.

    Args:
        url: The URL to open in the browser
    """
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = f"https://{url}"
        webbrowser.open(url)
        return f"✅ Opened {url} in your default browser."
    except Exception as e:
        return f"Error opening webpage in browser: {e}"


@tool
async def search_and_open(query: str, open_first: bool = False) -> str:
    """
    Searches the web and optionally opens the first result in browser.

    Args:
        query: The search query
        open_first: Whether to open the first result in browser
    """
    try:
        results = await _tavily_search(query, 3)

        formatted = f"🔍 Search Results for: '{query}'\n\n"
        first_url = None
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                if isinstance(result, dict):
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    content = result.get("content", "")
                    if i == 1:
                        first_url = url
                    formatted += f"{i}. **{title}**\n   URL: {url}\n   {content[:200]}...\n\n"

        if open_first and first_url:
            webbrowser.open(first_url)
            formatted += f"\n✅ Opened first result ({first_url}) in your browser."

        return formatted
    except Exception as e:
        return f"Error in search and open: {e}"


@tool
async def get_page_links(url: str, limit: int = 10) -> str:
    """
    Extracts all links from a webpage.

    Args:
        url: The URL of the webpage
        limit: Maximum number of links to return
    """
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.find_all("a", href=True)

        result = f"🔗 **Links found on {url}:**\n\n"
        count = 0
        for link in links:
            if count >= limit:
                break
            href = link["href"]
            text = link.get_text(strip=True)
            if href.startswith("/"):
                href = urljoin(url, href)
            elif not href.startswith("http"):
                continue
            if text:
                result += f"{count + 1}. [{text}]({href})\n"
            else:
                result += f"{count + 1}. {href}\n"
            count += 1

        return result if count > 0 else f"No links found on {url}"
    except Exception as e:
        return f"Error extracting links: {e}"


@tool
async def download_file(url: str, filename: str = None) -> str:
    """
    Downloads a file from a URL to the local system.

    Args:
        url: The URL of the file to download
        filename: Optional custom filename (will use URL filename if not provided)
    """
    try:
        if not filename:
            filename = url.split("/")[-1]
            if not filename or "." not in filename:
                filename = "downloaded_file"

        filename = os.path.basename(filename)
        if not filename:
            filename = "downloaded_file"

        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        filepath = os.path.join(downloads_dir, filename)

        if not os.path.abspath(filepath).startswith(os.path.abspath(downloads_dir) + os.sep):
            return "Error: Invalid filename — path traversal detected."

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        file_size = os.path.getsize(filepath)
        return f"✅ Downloaded {filename} ({file_size / (1024 * 1024):.2f} MB) to {filepath}"
    except Exception as e:
        return f"Error downloading file: {e}"


@tool
async def get_weather(location: str) -> str:
    """
    Gets current weather information for a specified location using wttr.in.

    Args:
        location: City name or location (e.g., "London", "New York", "Tokyo")
    """
    try:
        url = f"https://wttr.in/{location}?format=j1"
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        current = data["current_condition"][0]
        loc_info = data["nearest_area"][0]
        area_name = loc_info["areaName"][0]["value"]
        country = loc_info["country"][0]["value"]

        result = f"🌤️ **Weather for {area_name}, {country}**\n\n"
        result += f"🌡️ Temperature: {current['temp_C']}°C / {current['temp_F']}°F"
        result += f" (Feels like: {current['FeelsLikeC']}°C / {current['FeelsLikeF']}°F)\n"
        result += f"☁️ Conditions: {current['weatherDesc'][0]['value']}\n"
        result += f"💧 Humidity: {current['humidity']}%\n"
        result += f"💨 Wind Speed: {current['windspeedKmph']} km/h\n"
        return result
    except Exception as e:
        return f"Error getting weather: {e}. Please check the location name and try again."


@tool
async def get_weather_forecast(location: str, days: int = 3) -> str:
    """
    Gets weather forecast for a specified location.

    Args:
        location: City name or location
        days: Number of days to forecast (1-3)
    """
    try:
        days = max(1, min(3, days))
        url = f"https://wttr.in/{location}?format=j1"
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        loc_info = data["nearest_area"][0]
        area_name = loc_info["areaName"][0]["value"]
        country = loc_info["country"][0]["value"]

        result = f"📅 **{days}-Day Weather Forecast for {area_name}, {country}**\n\n"
        for i in range(min(days, len(data["weather"]))):
            day = data["weather"][i]
            hourly = day["hourly"][4]  # midday
            result += f"📆 **{day['date']}**\n"
            result += f"   🌡️ High: {day['maxtempC']}°C / {day['maxtempF']}°F"
            result += f" | Low: {day['mintempC']}°C / {day['mintempF']}°F\n"
            result += f"   ☁️ {hourly['weatherDesc'][0]['value']}\n\n"
        return result
    except Exception as e:
        return f"Error getting weather forecast: {e}"


@tool
async def get_latest_news(topic: str = None, max_results: int = 5) -> str:
    """
    Gets the latest news headlines using Tavily search.

    Args:
        topic: Optional topic to search for (e.g., "technology", "sports")
        max_results: Number of news items to return (1-10)
    """
    try:
        max_results = max(1, min(10, max_results))
        query = f"latest news about {topic}" if topic else "latest news headlines today"
        results = await _tavily_search(query, max_results)

        formatted = f"🔍 Search Results for: '{query}'\n\n"
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                if isinstance(result, dict):
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    content = result.get("content", "")
                    formatted += f"{i}. **{title}**\n   URL: {url}\n   {content[:200]}...\n\n"
                else:
                    formatted += f"{i}. {str(result)}\n\n"
        else:
            formatted += str(results)

        return f"📰 **Latest News**\n\n{formatted}"
    except Exception as e:
        return f"Error getting news: {e}"


@tool
async def translate_text(text: str, target_language: str = "en") -> str:
    """
    Translates text to the specified target language using MyMemory API.

    Args:
        text: Text to translate
        target_language: Target language code (e.g., "en", "es", "fr", "de", "ja")
    """
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"auto|{target_language}"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["responseStatus"] == 200:
            translated = data["responseData"]["translatedText"]
            detected = data["responseData"].get("detectedLanguage", "unknown")
            return f"🌐 **Translation**\n\n📝 Original: {text}\n✅ Translated ({detected} → {target_language}): {translated}"
        return "Translation failed. Please check the language code and try again."
    except Exception as e:
        return f"Error translating text: {e}"


@tool
async def get_currency_exchange(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Converts currency amounts using live exchange rates.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD", "EUR", "GBP")
        to_currency: Target currency code
    """
    try:
        from_code = from_currency.upper()
        to_code = to_currency.upper()
        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_code}&to={to_code}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        rates = data.get("rates", {})
        if to_code in rates:
            converted = rates[to_code]
            rate = converted / amount if amount else 0
            return (
                f"**Currency Conversion**\n\n"
                f"{amount} {from_code} = {converted:.2f} {to_code}\n"
                f"Exchange Rate: 1 {from_code} = {rate:.4f} {to_code}\n"
                f"Date: {data.get('date', 'N/A')}"
            )
        return "Currency conversion failed. Please check the currency codes."
    except Exception as e:
        return f"Error converting currency: {e}"


@tool
async def get_definition(word: str) -> str:
    """
    Gets the definition of a word using a dictionary API.

    Args:
        word: Word to define
    """
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        if not data:
            return f"No definition found for '{word}'."

        entry = data[0]
        word_text = entry["word"]
        phonetic = entry.get("phonetic", "")

        result = f"📖 **Definition of '{word_text}'**\n"
        result += f"🔊 Pronunciation: {phonetic}\n\n" if phonetic else "\n"

        for i in range(min(3, len(entry["meanings"]))):
            meaning = entry["meanings"][i]
            pos = meaning["partOfSpeech"]
            defn = meaning["definitions"][0]["definition"]
            result += f"**{pos.capitalize()}:**\n  • {defn}\n"
            if "example" in meaning["definitions"][0]:
                result += f'  📝 Example: "{meaning["definitions"][0]["example"]}"\n'
            result += "\n"

        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Word '{word}' not found in dictionary."
        return f"Error getting definition: {e}"
    except Exception as e:
        return f"Error getting definition: {e}"


@tool
async def check_website_status(url: str) -> str:
    """
    Checks if a website is online and responding, and provides response time.

    Args:
        url: URL of the website to check
    """
    try:
        import time as _time

        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = f"https://{url}"

        start = _time.monotonic()
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(url)
        elapsed_ms = (_time.monotonic() - start) * 1000

        return (
            f"🌐 **Website Status Check**\n\n"
            f"🔗 URL: {url}\n"
            f"✅ Status: Online ({response.status_code})\n"
            f"⏱️ Response Time: {elapsed_ms:.2f} ms\n"
            f"📄 Content Length: {len(response.content)} bytes"
        )
    except httpx.TimeoutException:
        return f"⏰ Timeout: {url} took too long to respond (>10 seconds)."
    except httpx.ConnectError:
        return f"❌ Connection Error: Unable to connect to {url}. The website might be down."
    except Exception as e:
        return f"❌ Error checking website: {e}"


@tool
async def shorten_url(long_url: str) -> str:
    """
    Shortens a long URL using TinyURL.

    Args:
        long_url: The long URL to shorten
    """
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            short_url = response.text.strip()

        return f"🔗 **URL Shortened**\n\n📎 Original: {long_url}\n✂️ Shortened: {short_url}"
    except Exception as e:
        return f"Error shortening URL: {e}"


@tool
async def search_wikipedia(query: str, sentences: int = 5) -> str:
    """
    Searches Wikipedia and returns a summary of the topic.

    Args:
        query: Topic or question to look up on Wikipedia
        sentences: Number of sentences to return in the summary (1-10)
    """
    try:
        sentences = max(1, min(10, sentences))
        api_url = "https://en.wikipedia.org/w/api.php"

        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: search for the article title
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
            results = search_resp.json().get("query", {}).get("search", [])
            if not results:
                return f"No Wikipedia article found for: {query}"

            page_title = results[0]["title"]

            # Step 2: fetch the article extract
            extract_resp = await client.get(
                api_url,
                params={
                    "action": "query",
                    "titles": page_title,
                    "prop": "extracts",
                    "exsentences": sentences,
                    "exintro": True,
                    "explaintext": True,
                    "format": "json",
                },
            )
            extract_resp.raise_for_status()
            pages = extract_resp.json().get("query", {}).get("pages", {})
            page = next(iter(pages.values()))
            extract = page.get("extract", "No content available.")

        wiki_url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
        return f"📚 **Wikipedia: {page_title}**\n\n{extract}\n\n🔗 Read more: {wiki_url}"
    except Exception as e:
        return f"Error fetching Wikipedia article: {e}"


@tool
async def get_stock_price(ticker: str) -> str:
    """
    Gets the current stock price and basic info for a given ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, TSLA, MSFT, GOOGL)
    """
    try:
        ticker = ticker.upper().strip()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        result_data = data.get("chart", {}).get("result", [])
        if not result_data:
            return f"No data found for ticker: {ticker}. Check the symbol and try again."

        meta = result_data[0].get("meta", {})
        current_price = meta.get("regularMarketPrice", "N/A")
        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", "N/A"))
        currency = meta.get("currency", "USD")
        name = meta.get("longName") or meta.get("shortName") or ticker
        exchange = meta.get("exchangeName", "")

        change = ""
        if current_price != "N/A" and prev_close != "N/A":
            diff = current_price - prev_close
            pct = (diff / prev_close) * 100
            arrow = "📈" if diff >= 0 else "📉"
            change = f"{arrow} Change: {diff:+.2f} ({pct:+.2f}%)\n"

        return (
            f"📊 **{name} ({ticker})**\n"
            f"💰 Price: {current_price} {currency}\n"
            f"📋 Prev Close: {prev_close} {currency}\n"
            f"{change}"
            f"🏛️ Exchange: {exchange}"
        )
    except Exception as e:
        return f"Error fetching stock price for {ticker}: {e}"


@tool
async def search_reddit(query: str, subreddit: str = "", limit: int = 5) -> str:
    """
    Searches Reddit for posts matching a query.

    Args:
        query: Search query
        subreddit: Optional subreddit name (e.g., 'technology', 'python'). Leave empty to search all.
        limit: Number of results (1-10)
    """
    try:
        limit = max(1, min(10, limit))
        headers = {"User-Agent": "SentinelAI/1.0"}
        base_url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            if subreddit
            else "https://www.reddit.com/search.json"
        )
        params = {"q": query, "sort": "relevance", "limit": limit, "restrict_sr": bool(subreddit)}

        async with httpx.AsyncClient(headers=headers, timeout=10, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            posts = response.json().get("data", {}).get("children", [])

        if not posts:
            return f"No Reddit posts found for: {query}"

        sub_label = f"r/{subreddit}" if subreddit else "Reddit"
        result = f"🔴 **Reddit Search: '{query}' on {sub_label}**\n\n"
        for i, post_data in enumerate(posts, 1):
            p = post_data.get("data", {})
            title = p.get("title", "No title")
            sub = p.get("subreddit_name_prefixed", "")
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)
            permalink = "https://reddit.com" + p.get("permalink", "")
            result += (
                f"{i}. **{title}**\n"
                f"   {sub} · ⬆️ {score} · 💬 {num_comments} comments\n"
                f"   🔗 {permalink}\n\n"
            )
        return result.strip()
    except Exception as e:
        return f"Error searching Reddit: {e}"


# ---------------------------------------------------------------------------
# Tool list
# ---------------------------------------------------------------------------

browser_tools = [
    tavily_web_search,
    scrape_webpage,
    open_webpage_in_browser,
    search_and_open,
    get_page_links,
    download_file,
    get_weather,
    get_weather_forecast,
    get_latest_news,
    translate_text,
    get_currency_exchange,
    get_definition,
    check_website_status,
    shorten_url,
    search_wikipedia,
    get_stock_price,
    search_reddit,
]
