# src/tools/browser_tools.py

import requests
import webbrowser
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Enhanced Search Tools ---

@tool
def tavily_web_search(query: str, max_results: int = 5) -> str:
    """
    Performs a comprehensive web search using Tavily API.
    Returns detailed search results with summaries and sources.
    
    Args:
        query: The search query
        max_results: Number of results to return (1-10)
    """
    try:
        if max_results < 1 or max_results > 10:
            max_results = 5
        
        tavily = TavilySearchResults(max_results=max_results)
        results = tavily.run(query)
        
        if not results:
            return f"No search results found for: {query}"
        
        # Format results nicely
        formatted_results = f"🔍 Search Results for: '{query}'\n\n"
        
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                if isinstance(result, dict):
                    title = result.get('title', 'No title')
                    url = result.get('url', 'No URL')
                    content = result.get('content', 'No content available')
                    
                    formatted_results += f"{i}. **{title}**\n"
                    formatted_results += f"   URL: {url}\n"
                    formatted_results += f"   Summary: {content[:200]}...\n\n"
                else:
                    formatted_results += f"{i}. {str(result)}\n\n"
        else:
            formatted_results += str(results)
        
        return formatted_results
        
    except Exception as e:
        return f"Error performing web search: {e}"


@tool
def scrape_webpage(url: str) -> str:
    """
    Scrapes and extracts text content from a webpage.
    Returns the main text content, title, and metadata.
    
    Args:
        url: The URL of the webpage to scrape
    """
    try:
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return "Invalid URL provided. Please include http:// or https://"
        
        # Set headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Make request with timeout
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "No title found"
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract main content
        main_content = ""
        
        # Try to find main content areas
        content_selectors = [
            'article', 'main', '.content', '#content', 
            '.post', '.entry-content', '.article-body'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                main_content = content_area.get_text(separator='\n', strip=True)
                break
        
        # If no specific content area found, get body text
        if not main_content:
            body = soup.find('body')
            if body:
                main_content = body.get_text(separator='\n', strip=True)
        
        # Clean up the text
        lines = [line.strip() for line in main_content.split('\n') if line.strip()]
        cleaned_content = '\n'.join(lines)
        
        # Truncate if too long
        if len(cleaned_content) > 2000:
            cleaned_content = cleaned_content[:2000] + "... [Content truncated]"
        
        result = f"📄 **{title_text}**\n"
        result += f"🔗 URL: {url}\n\n"
        result += f"📝 **Content:**\n{cleaned_content}"
        
        return result
        
    except requests.exceptions.Timeout:
        return f"Timeout error: The webpage took too long to respond - {url}"
    except requests.exceptions.RequestException as e:
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
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            # Add https if no scheme provided
            url = f"https://{url}"
        
        webbrowser.open(url)
        return f"✅ Opened {url} in your default browser."
        
    except Exception as e:
        return f"Error opening webpage in browser: {e}"


@tool
def search_and_open(query: str, open_first: bool = False) -> str:
    """
    Searches the web and optionally opens the first result in browser.
    
    Args:
        query: The search query
        open_first: Whether to open the first result in browser
    """
    try:
        # Perform search
        search_results = tavily_web_search(query, max_results=3)
        
        if open_first and "URL:" in search_results:
            # Extract first URL from results
            lines = search_results.split('\n')
            first_url = None
            
            for line in lines:
                if "URL:" in line:
                    first_url = line.replace("URL:", "").strip()
                    break
            
            if first_url:
                webbrowser.open(first_url)
                return f"{search_results}\n\n✅ Opened first result ({first_url}) in your browser."
        
        return search_results
        
    except Exception as e:
        return f"Error in search and open: {e}"


@tool
def get_page_links(url: str, limit: int = 10) -> str:
    """
    Extracts all links from a webpage.
    
    Args:
        url: The URL of the webpage
        limit: Maximum number of links to return
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        result = f"🔗 **Links found on {url}:**\n\n"
        count = 0
        
        for link in links:
            if count >= limit:
                break
                
            href = link['href']
            text = link.get_text(strip=True)
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(url, href)
            elif not href.startswith('http'):
                continue
            
            if text:
                result += f"{count + 1}. [{text}]({href})\n"
            else:
                result += f"{count + 1}. {href}\n"
            
            count += 1
        
        if count == 0:
            return f"No links found on {url}"
        
        return result
        
    except Exception as e:
        return f"Error extracting links: {e}"


@tool
def download_file(url: str, filename: str = None) -> str:
    """
    Downloads a file from a URL to the local system.

    Args:
        url: The URL of the file to download
        filename: Optional custom filename (will use URL filename if not provided)
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Determine filename
        if not filename:
            filename = url.split('/')[-1]
            if not filename or '.' not in filename:
                filename = "downloaded_file"

        # Create downloads directory if it doesn't exist
        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)

        filepath = os.path.join(downloads_dir, filename)

        # Download file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / (1024 * 1024)

        return f"✅ Downloaded {filename} ({file_size_mb:.2f} MB) to {filepath}"

    except Exception as e:
        return f"Error downloading file: {e}"


@tool
def get_weather(location: str) -> str:
    """
    Gets current weather information for a specified location.
    Uses wttr.in free weather API.

    Args:
        location: City name or location (e.g., "London", "New York", "Tokyo")
    """
    try:
        # Use wttr.in API (no API key required)
        url = f"https://wttr.in/{location}?format=j1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract current weather
        current = data['current_condition'][0]
        temp_c = current['temp_C']
        temp_f = current['temp_F']
        feels_like_c = current['FeelsLikeC']
        feels_like_f = current['FeelsLikeF']
        weather_desc = current['weatherDesc'][0]['value']
        humidity = current['humidity']
        wind_speed = current['windspeedKmph']

        # Extract location info
        location_info = data['nearest_area'][0]
        area_name = location_info['areaName'][0]['value']
        country = location_info['country'][0]['value']

        result = f"🌤️ **Weather for {area_name}, {country}**\n\n"
        result += f"🌡️ Temperature: {temp_c}°C / {temp_f}°F (Feels like: {feels_like_c}°C / {feels_like_f}°F)\n"
        result += f"☁️ Conditions: {weather_desc}\n"
        result += f"💧 Humidity: {humidity}%\n"
        result += f"💨 Wind Speed: {wind_speed} km/h\n"

        return result

    except Exception as e:
        return f"Error getting weather: {e}. Please check the location name and try again."


@tool
def get_weather_forecast(location: str, days: int = 3) -> str:
    """
    Gets weather forecast for a specified location.

    Args:
        location: City name or location
        days: Number of days to forecast (1-3)
    """
    try:
        if days < 1 or days > 3:
            days = 3

        url = f"https://wttr.in/{location}?format=j1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract location info
        location_info = data['nearest_area'][0]
        area_name = location_info['areaName'][0]['value']
        country = location_info['country'][0]['value']

        result = f"📅 **{days}-Day Weather Forecast for {area_name}, {country}**\n\n"

        for i in range(min(days, len(data['weather']))):
            day_data = data['weather'][i]
            date = day_data['date']
            max_temp_c = day_data['maxtempC']
            min_temp_c = day_data['mintempC']
            max_temp_f = day_data['maxtempF']
            min_temp_f = day_data['mintempF']

            # Get midday weather description
            hourly = day_data['hourly'][4]  # 12:00 PM
            desc = hourly['weatherDesc'][0]['value']

            result += f"📆 **{date}**\n"
            result += f"   🌡️ High: {max_temp_c}°C / {max_temp_f}°F | Low: {min_temp_c}°C / {min_temp_f}°F\n"
            result += f"   ☁️ {desc}\n\n"

        return result

    except Exception as e:
        return f"Error getting weather forecast: {e}"


@tool
def get_latest_news(topic: str = None, max_results: int = 5) -> str:
    """
    Gets the latest news headlines using Tavily search.

    Args:
        topic: Optional topic to search for (e.g., "technology", "sports", "politics")
        max_results: Number of news items to return (1-10)
    """
    try:
        if max_results < 1 or max_results > 10:
            max_results = 5

        # Use Tavily for news search
        if topic:
            query = f"latest news about {topic}"
        else:
            query = "latest news headlines today"

        search_result = tavily_web_search(query, max_results=max_results)

        return f"📰 **Latest News**\n\n{search_result}"

    except Exception as e:
        return f"Error getting news: {e}"


@tool
def translate_text(text: str, target_language: str = "en") -> str:
    """
    Translates text to the specified target language using a free translation API.

    Args:
        text: Text to translate
        target_language: Target language code (e.g., "en", "es", "fr", "de", "ja", "zh")
    """
    try:
        # Use MyMemory Translation API (free, no key required)
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': f"auto|{target_language}"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data['responseStatus'] == 200:
            translated = data['responseData']['translatedText']
            detected_lang = data['responseData'].get('detectedLanguage', 'unknown')

            return f"🌐 **Translation**\n\n📝 Original: {text}\n✅ Translated ({detected_lang} → {target_language}): {translated}"
        else:
            return f"Translation failed. Please check the language code and try again."

    except Exception as e:
        return f"Error translating text: {e}"


@tool
def get_currency_exchange(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Converts currency amounts using live exchange rates.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD", "EUR", "GBP")
        to_currency: Target currency code
    """
    try:
        # Use exchangerate.host API (free, no key required)
        url = f"https://api.exchangerate.host/convert?from={from_currency}&to={to_currency}&amount={amount}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get('success'):
            result_amount = data['result']
            rate = data['info']['rate']
            date = data['date']

            return f"💱 **Currency Conversion**\n\n{amount} {from_currency} = {result_amount:.2f} {to_currency}\n📊 Exchange Rate: 1 {from_currency} = {rate:.4f} {to_currency}\n📅 Date: {date}"
        else:
            return f"Currency conversion failed. Please check the currency codes."

    except Exception as e:
        return f"Error converting currency: {e}"


@tool
def get_definition(word: str) -> str:
    """
    Gets the definition of a word using a dictionary API.

    Args:
        word: Word to define
    """
    try:
        # Use Free Dictionary API
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data and len(data) > 0:
            entry = data[0]
            word_text = entry['word']
            phonetic = entry.get('phonetic', '')

            result = f"📖 **Definition of '{word_text}'**\n"
            if phonetic:
                result += f"🔊 Pronunciation: {phonetic}\n\n"
            else:
                result += "\n"

            # Get first 3 meanings
            meanings_count = min(3, len(entry['meanings']))
            for i in range(meanings_count):
                meaning = entry['meanings'][i]
                part_of_speech = meaning['partOfSpeech']
                definition = meaning['definitions'][0]['definition']

                result += f"**{part_of_speech.capitalize()}:**\n"
                result += f"  • {definition}\n\n"

                # Add example if available
                if 'example' in meaning['definitions'][0]:
                    example = meaning['definitions'][0]['example']
                    result += f"  📝 Example: \"{example}\"\n\n"

            return result
        else:
            return f"No definition found for '{word}'."

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return f"Word '{word}' not found in dictionary."
        return f"Error getting definition: {e}"
    except Exception as e:
        return f"Error getting definition: {e}"


@tool
def check_website_status(url: str) -> str:
    """
    Checks if a website is online and responding, and provides response time.

    Args:
        url: URL of the website to check
    """
    try:
        import time as time_module

        # Ensure URL has scheme
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = f"https://{url}"

        start_time = time_module.time()
        response = requests.get(url, timeout=10)
        end_time = time_module.time()

        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        result = f"🌐 **Website Status Check**\n\n"
        result += f"🔗 URL: {url}\n"
        result += f"✅ Status: Online ({response.status_code})\n"
        result += f"⏱️ Response Time: {response_time:.2f} ms\n"
        result += f"📄 Content Length: {len(response.content)} bytes\n"

        return result

    except requests.exceptions.Timeout:
        return f"⏰ Timeout: {url} took too long to respond (>10 seconds)."
    except requests.exceptions.ConnectionError:
        return f"❌ Connection Error: Unable to connect to {url}. The website might be down or the URL is incorrect."
    except Exception as e:
        return f"❌ Error checking website: {e}"


@tool
def shorten_url(long_url: str) -> str:
    """
    Shortens a long URL using a URL shortening service.

    Args:
        long_url: The long URL to shorten
    """
    try:
        # Use TinyURL API (free, no key required)
        api_url = f"http://tinyurl.com/api-create.php?url={long_url}"

        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        short_url = response.text.strip()

        return f"🔗 **URL Shortened**\n\n📎 Original: {long_url}\n✂️ Shortened: {short_url}"

    except Exception as e:
        return f"Error shortening URL: {e}"


# Enhanced browser tools list
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
    shorten_url
]