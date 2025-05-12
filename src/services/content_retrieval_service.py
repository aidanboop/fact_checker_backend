# /home/ubuntu/fact_checker_backend/src/services/content_retrieval_service.py

import asyncio
from playwright.async_api import async_playwright

async def retrieve_content_from_url(url: str) -> str:
    """
    Retrieves the main textual content from a given URL.

    Args:
        url: The URL to fetch content from.

    Returns:
        The extracted textual content as a string, or an error message if retrieval fails.
    """
    if not url or not url.startswith(("http://", "https://")):
        return "Error: Invalid URL provided."

    content = ""
    async with async_playwright() as p:
        # browser = await p.chromium.launch(headless=True)
        browser = await p.firefox.launch(headless=True) # Sticking with Firefox
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000) # 15 seconds timeout
            
            # Attempt to extract main content. This is a heuristic and might need refinement.
            # Common patterns for main content: <article>, <main>, role="main"
            # Or, remove common noise like <nav>, <header>, <footer>, <aside>, <script>, <style>
            
            # Try to get text from common main content containers first
            main_selectors = ["article", "main", "[role=\"main\"]", ".post-content", ".entry-content"]
            for selector in main_selectors:
                main_element = await page.query_selector(selector)
                if main_element:
                    content = await main_element.inner_text()
                    break
            
            if not content:
                # If no specific main element found, try to get all body text and clean it up
                # This is a very basic cleanup, more sophisticated methods exist (e.g., readability.js port)                await page.evaluate("() => { document.querySelectorAll(\"script, style, nav, header, footer, aside, form, [aria-hidden=\\\"true\\\"]").forEach(el => el.remove()); }")
                body_element = await page.query_selector("body")
                if body_element:
                    content = await body_element.inner_text()

            # Basic cleaning of excessive newlines
            if content:
                content = "\n".join([line.strip() for line in content.split("\n") if line.strip()])
                content = content[:10000] # Limit content length to avoid overly long processing

        except Exception as e:
            print(f"Error retrieving content from {url}: {e}")
            content = f"Error: Could not retrieve content from {url}. Details: {str(e)[:100]}"
        finally:
            await browser.close()
            
    return content.strip()

# Example usage (for testing purposes)
async def main_test():
    # Test with a known good URL if possible, or a placeholder
    # For a real test, you would use a URL from the search_service output
    test_url = "https://www.wikipedia.org/" # Example URL
    print(f"Retrieving content from: {test_url}")
    page_content = await retrieve_content_from_url(test_url)
    
    if page_content.startswith("Error:"):
        print(page_content)
    else:
        print(f"Retrieved Content (first 500 chars):\n{page_content[:500]}...")

if __name__ == '__main__':
    asyncio.run(main_test())

