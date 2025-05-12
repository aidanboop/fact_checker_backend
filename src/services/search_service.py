# /home/ubuntu/fact_checker_backend/src/services/search_service.py

import asyncio
from playwright.async_api import async_playwright
import urllib.parse

async def perform_web_search(statement: str, num_results: int = 3) -> list[dict]:
    """
    Performs a web search for the given statement and returns a list of search results.
    Uses Brave Search.
    """
    query = statement
    results = []
    debug_html_path = "/home/ubuntu/debug_search_page.html"
    screenshot_path = "/home/ubuntu/debug_search_screenshot.png"
    print(f"Starting web search for query: {query} using Brave Search")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        })

        page_html = ""
        try:
            search_url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}&source=web"
            print(f"Attempting to navigate to: {search_url}")
            await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            print(f"Navigation to {search_url} initially completed.")

            await page.wait_for_timeout(3000) # Allow some time for dynamic content if any

            page_html = await page.content()
            with open(debug_html_path, "w", encoding="utf-8") as f_html:
                f_html.write(page_html)
            print(f"Page HTML saved to {debug_html_path} for inspection.")
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

            # Refined selectors for Brave Search based on HTML inspection
            # Common container for results: div.snippet, sometimes with data-pos
            # Title link: a inside div.snippet-title, or a.result-header
            # Snippet: p.snippet-description or div.snippet-content
            
            result_elements = await page.query_selector_all("div.snippet[data-pos], div.search-result.snippet")
            if not result_elements:
                 result_elements = await page.query_selector_all("div.results > div.snippet") # More general fallback
            
            print(f"Found {len(result_elements)} potential result elements.")

            count = 0
            for el_idx, el in enumerate(result_elements):
                if count >= num_results:
                    break
                
                title, link, snippet_text = "N/A", "N/A", "N/A"
                try:
                    # Try to find title and link
                    title_element = await el.query_selector("a.snippet-title")
                    if not title_element:
                        title_element = await el.query_selector("div.title > a") # From previous attempt
                    if not title_element:
                        title_element = await el.query_selector("h3.title a") # Another common pattern
                    if not title_element:
                        title_element = await el.query_selector("div[data-type=\"web\"] a.result-header") # More specific Brave selector
                    if not title_element: # Last resort for title link
                        title_element = await el.query_selector("a[href]") # Broadest link selector within snippet

                    # Try to find snippet
                    snippet_element = await el.query_selector("p.snippet-description")
                    if not snippet_element:
                        snippet_element = await el.query_selector("div.snippet-content")
                    if not snippet_element:
                        snippet_element = await el.query_selector("div.desc") # From previous attempt
                    if not snippet_element: # Broadest text container
                        snippet_element = el # Use the whole element if no specific snippet found

                    if title_element:
                        title_text_candidate = await title_element.inner_text()
                        link_candidate = await title_element.get_attribute("href")
                        
                        # Filter out non-result links like "Cached" or internal anchors
                        if link_candidate and not link_candidate.startswith("#") and ("cache" not in link_candidate.lower()):
                            title = title_text_candidate
                            link = link_candidate
                    
                    if snippet_element:
                        snippet_text = await snippet_element.inner_text()
                    
                    if title and title != "N/A" and link and link != "N/A":
                        if link.startswith("//"):
                            link = f"https:{link}"
                        elif not link.startswith("http"):
                            base_url_parts = urllib.parse.urlparse(search_url)
                            link = urllib.parse.urljoin(f"{base_url_parts.scheme}://{base_url_parts.netloc}", link)
                            
                        if link.startswith("http"):
                            # Basic cleaning of snippet
                            snippet_text = " ".join(snippet_text.split()).strip()
                            results.append({
                                "title": title.strip(),
                                "link": link.strip(),
                                "snippet": snippet_text[:500] # Limit snippet length
                            })
                            count += 1
                            print(f"  Added result: {title.strip()} - {link.strip()}")
                        else:
                            print(f"  Skipped (non-HTTP or invalid link): {title.strip()} - {link}")
                    else:
                        # print(f"  Skipped (missing title/link element or invalid link): Element index {el_idx}")
                        pass # Avoid too much noise for non-matching elements

                except Exception as e_el_proc:
                    print(f"Error processing element {el_idx+1}: {e_el_proc}")
                    continue
            
            if not results and len(result_elements) > 0:
                print("Found result containers, but failed to extract details. Selectors might need further refinement.")

        except Exception as e:
            print(f"An error occurred during web search: {e}")
            import traceback
            traceback.print_exc()
            try:
                if not page_html:
                    page_html_on_error = await page.content()
                    with open(debug_html_path, "w", encoding="utf-8") as f_html_err:
                        f_html_err.write(page_html_on_error)
                    print(f"Page HTML on error saved to {debug_html_path}")
                await page.screenshot(path=screenshot_path)
                print(f"Screenshot on error saved to {screenshot_path}")
            except Exception as e_save:
                print(f"Could not save HTML/Screenshot on error: {e_save}")

            if not results:
                results.append({"title": "Error", "link": "", "snippet": f"Failed to perform search: {str(e)[:200]}"})

        finally:
            await browser.close()
    
    print(f"perform_web_search returning {len(results)} results.")
    return results

async def main_test():
    test_statements = [
        "The sky is blue during the day.",
        "Paris is the capital of France",
        "What is the tallest mountain in the world?"
    ]
    for stmt in test_statements:
        print(f"\n== Running test for: \t{stmt} ==")
        search_results = await perform_web_search(stmt)
        if search_results and not (len(search_results) == 1 and search_results[0]['title'] == "Error"):
            for i, res in enumerate(search_results):
                print(f"Result {i+1}:")
                print(f"  Title: {res['title']}")
                print(f"  Link: {res['link']}")
                print(f"  Snippet: {res['snippet']}\n")
        else:
            print("No valid results found or an error occurred during search.")

if __name__ == "__main__":
    asyncio.run(main_test())

