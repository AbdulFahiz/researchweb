import httpx
from bs4 import BeautifulSoup
from typing import List, Dict
from collections import OrderedDict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# In-memory cache for search results (max 30 entries)
search_cache = OrderedDict()

async def duckduckgo_search(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Performs an improved search using DuckDuckGo with better result filtering.
    """
    # Check cache first for faster repeat searches
    cache_key = f"{query}:{max_results}"
    if cache_key in search_cache:
        return search_cache[cache_key]
    
    # Enhance query for better results
    enhanced_query = query.replace(' ', '+')
    search_url = f"https://html.duckduckgo.com/html/?q={enhanced_query}"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15.0) as client:
        try:
            response = await client.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('div', class_='result'):
                title_tag = result.find('a', class_='result__a')
                snippet_tag = result.find('a', class_='result__snippet')
                url_tag = result.find('a', class_='result__url')

                if title_tag and snippet_tag and url_tag:
                    title = title_tag.get_text(strip=True)
                    snippet = snippet_tag.get_text(strip=True)
                    url = url_tag['href']
                    
                    # Filter out irrelevant results
                    if len(snippet) < 20 or 'advertisement' in snippet.lower():
                        continue
                    
                    # DDG html urls are relative
                    if url.startswith("//"):
                        url = "https:" + url
                    elif not url.startswith("http"):
                        continue

                    results.append({"title": title, "snippet": snippet, "url": url})
                    if len(results) >= max_results:
                        break
            
            # Cache the results (keep cache size manageable)
            if len(search_cache) >= 30:
                search_cache.popitem(last=False)  # Remove oldest entry
            search_cache[cache_key] = results
            return results
        except httpx.HTTPStatusError as e:
            print(f"HTTP error during DDG search: {e}")
            return []
        except Exception as e:
            print(f"An error occurred during DDG search: {e}")
            return []


async def scrape_page(client: httpx.AsyncClient, url: str, max_chars: int = 2000) -> str:
    """
    Scrapes and cleanses the text content of a webpage for research quality.
    Tries fast timeout first (8s), then longer timeout (12s) once if needed.
    Uses provided client for connection pooling.
    """
    try:
        # Fast attempt first (8s)
        response = None
        try:
            response = await client.get(url, timeout=8.0)
            response.raise_for_status()
        except httpx.TimeoutException:
            # One retry with longer timeout (12s)
            try:
                response = await client.get(url, timeout=12.0)
                response.raise_for_status()
            except Exception:
                return "Error: Page request timed out"

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script, style, nav, footer, header, ads, and other non-content tags
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
            element.decompose()
        
        # Try to find main content area first
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main', 'body'])
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            body = soup.find('body')
            if body:
                text = body.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
        
        if not text or len(text) < 50:
            return "Error: Page content too short or empty"
        
        # Clean up excessive whitespace
        text = ' '.join(text.split())
        # Limit characters but try to end at a sentence boundary
        if len(text) > max_chars:
            text = text[:max_chars].rsplit('.', 1)[0] + '.' if '.' in text[:max_chars] else text[:max_chars]
        
        return text
    except httpx.HTTPStatusError as e:
        return f"Error: Page not found (Status {e.response.status_code})"
    except httpx.RequestError as e:
        return f"Error: Could not reach the page"
    except Exception as e:
        return f"Error: Failed to process page"


async def wikipedia_search(client: httpx.AsyncClient, query: str) -> str:
    """
    Fetches the summary of a Wikipedia page using provided client.
    """
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("extract", "Summary not found.")
    except httpx.HTTPStatusError:
        return "Could not find a Wikipedia page for that topic."
    except Exception as e:
        return f"An error occurred during Wikipedia search: {e}"
