import aiohttp
import json
import asyncio
import time
import os
from dotenv import load_dotenv


load_dotenv()


async def web_search(query: str, depth: str = "standard", output_type: str = "searchResults") -> str:
    """
    Perform a web search using Linkup API and return summarized results.
    
    This tool searches the web for current information using Linkup's search API.
    Perfect for finding up-to-date information about insurance products, regulations, etc.
    
    Args:
        query (str): The search query string (e.g., "Prudential insurance products Vietnam")
        depth (str): Search depth - "standard" (default) or "deep" for more comprehensive results
        output_type (str): Response format - "searchResults" (default), "sourcedAnswer", or "structured"
    
    Returns:
        str: Formatted search results with titles, descriptions, and URLs
    """
    try:
        # Get Linkup API key from environment variable
        LINKUP_API_KEY = os.environ.get("LINKUP_API_KEY")
        if not LINKUP_API_KEY:
            return "Error: LINKUP_API_KEY environment variable not set. Please set your Linkup API key."
        
        async with aiohttp.ClientSession() as session:
            url = "https://api.linkup.so/v1/search"
            headers = {
                "Authorization": f"Bearer {LINKUP_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "q": query,
                "depth": depth,
                "outputType": output_type
            }
            
            async with session.post(
                url, 
                headers=headers, 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    results = []
                    
                    # Handle different output types
                    if output_type == "sourcedAnswer" and "answer" in data:
                        results.append(f"**Answer:**\n{data['answer']}")
                        if "sources" in data:
                            results.append("\n**Sources:**")
                            for i, source in enumerate(data["sources"][:5], 1):
                                results.append(f"{i}. {source.get('name', 'Unknown')} - {source.get('url', '')}")
                    
                    elif output_type == "searchResults" and "results" in data:
                        results.append("**Search Results:**")
                        for i, result in enumerate(data["results"][:10], 1):
                            title = result.get("name", "No title")
                            url_link = result.get("url", "")
                            content = result.get("content", "No description available")
                            
                            results.append(f"\n{i}. **{title}**")
                            results.append(f"   {content[:200]}...")  # Truncate long descriptions
                            results.append(f"   🔗 {url_link}")
                    
                    elif output_type == "structured" and "structured" in data:
                        results.append(f"**Structured Answer:**\n{json.dumps(data['structured'], indent=2)}")
                    
                    if results:
                        return "\n".join(results)
                    else:
                        return f"No results found for '{query}'. Try rephrasing your search query."
                
                elif response.status == 401:
                    return "Error: Invalid Linkup API key. Please check your LINKUP_API_KEY."
                elif response.status == 429:
                    return "Error: Rate limit exceeded. Please try again later."
                else:
                    error_text = await response.text()
                    return f"Search failed with status {response.status}: {error_text}"
                    
    except aiohttp.ClientError as e:
        return f"Network error during search: {str(e)}"
    except json.JSONDecodeError:
        return "Error parsing search results from Linkup API"
    except asyncio.TimeoutError:
        return "Search request timed out. Please try again with a simpler query."
    except Exception as e:
        return f"Error performing web search: {str(e)}"


async def web_search_alternative(query: str) -> str:
    """
    Alternative: Using HTML scraping with DuckDuckGo (no API key needed).
    Falls back to this if Brave API is not available.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://html.duckduckgo.com/html/"
            data = {"q": query}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Simple HTML parsing for results
                    from html.parser import HTMLParser
                    
                    class DDGParser(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.results = []
                            self.current_result = {}
                            self.in_result = False
                            self.in_title = False
                            self.in_snippet = False
                            
                        def handle_starttag(self, tag, attrs):
                            attrs_dict = dict(attrs)
                            if tag == "a" and attrs_dict.get("class") == "result__a":
                                self.in_title = True
                                self.current_result = {"url": attrs_dict.get("href", "")}
                            elif tag == "a" and attrs_dict.get("class") == "result__snippet":
                                self.in_snippet = True
                        
                        def handle_data(self, data):
                            if self.in_title:
                                self.current_result["title"] = data.strip()
                            elif self.in_snippet:
                                self.current_result["snippet"] = data.strip()
                        
                        def handle_endtag(self, tag):
                            if tag == "a" and self.in_title:
                                self.in_title = False
                            elif tag == "a" and self.in_snippet:
                                self.in_snippet = False
                                if self.current_result:
                                    self.results.append(self.current_result)
                                    self.current_result = {}
                    
                    parser = DDGParser()
                    parser.feed(html)
                    
                    if parser.results:
                        results = ["**Search Results:**"]
                        for i, result in enumerate(parser.results[:5], 1):
                            results.append(f"\n{i}. **{result.get('title', 'No title')}**")
                            results.append(f"   {result.get('snippet', 'No description')}")
                            results.append(f"   Source: {result.get('url', '')}")
                        return "\n".join(results)
                    else:
                        return f"No results found for '{query}'."
                else:
                    return f"Search failed with status code: {response.status}"
                    
    except Exception as e:
        return f"Error performing web search: {str(e)}"


# Example usage:
if __name__ == "__main__":
    start_time = time.time()
    query = "Các sản phẩm bảo hiểm của Prudential tại Việt Nam"
    
    # Try using Linkup API first
    result = asyncio.run(web_search(query, depth="deep", output_type="searchResults"))
    print(result)

    end_time = time.time()
    print(f"\nSearch took {end_time - start_time:.2f} seconds")