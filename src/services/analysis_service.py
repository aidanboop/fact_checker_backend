# /home/ubuntu/fact_checker_backend/src/services/analysis_service.py

import re

# Basic predefined lists for domain reputation (very simplified)
REPUTABLE_DOMAINS_KEYWORDS = ["wikipedia.org", "reuters.com", "apnews.com", "bbc.com", "nytimes.com", "wsj.com", ".gov", ".edu"]
LESS_REPUTABLE_KEYWORDS = ["blog", "forum", "personal", "conspiracy", "rumor"]

# Keywords for contradiction and confirmation
CONFIRMATION_KEYWORDS = ["is true", "confirmed", "fact", "accurate", "correct", "verified", "evidence shows", "supported by data"]
CONTRADICTION_KEYWORDS = ["is false", "not true", "incorrect", "hoax", "myth", "debunked", "misinformation", "unsubstantiated", "no evidence"]

async def analyze_content_for_statement(statement: str, search_results: list[dict], retrieved_contents: list[dict]) -> dict:
    """
    Analyzes the retrieved web content against the user's statement to determine
    credibility and a confidence score.

    Args:
        statement: The user's original statement.
        search_results: List of dicts from search_service (title, link, snippet).
        retrieved_contents: List of dicts, each with {"url": str, "content": str}.

    Returns:
        A dictionary containing:
        - "is_true": boolean or None (if inconclusive)
        - "confidence_score": integer (0-100)
        - "reasoning": string explaining the score
        - "supporting_snippets": list of relevant snippets from sources
    """
    statement_lower = statement.lower()
    statement_keywords = set(re.findall(r'\b\w+\b', statement_lower))

    total_score = 0
    max_possible_score = 0
    sources_analyzed = 0
    confirming_sources = 0
    contradicting_sources = 0
    supporting_snippets_for_response = []

    # Normalize retrieved_contents to a dictionary for easier lookup by URL
    content_map = {item["url"]: item["content"] for item in retrieved_contents if item["content"] and not item["content"].startswith("Error:")}

    for result in search_results:
        url = result.get("link")
        snippet = result.get("snippet", "").lower()
        page_content = content_map.get(url, "").lower()

        if not page_content and not snippet: # Skip if no content or snippet
            continue
        
        sources_analyzed += 1
        current_source_score = 0
        max_source_score = 100 # Max score per source

        # 1. Keyword Matching (in snippet and full content)
        matched_keywords_snippet = sum(1 for kw in statement_keywords if kw in snippet) / len(statement_keywords) if statement_keywords else 0
        matched_keywords_content = sum(1 for kw in statement_keywords if kw in page_content) / len(statement_keywords) if statement_keywords and page_content else 0
        keyword_score = (matched_keywords_snippet * 0.3 + matched_keywords_content * 0.7) * 30 # Max 30 points
        current_source_score += keyword_score

        # 2. Confirmation/Contradiction Keywords
        confirmation_found = any(phrase in page_content or phrase in snippet for phrase in CONFIRMATION_KEYWORDS)
        contradiction_found = any(phrase in page_content or phrase in snippet for phrase in CONTRADICTION_KEYWORDS)

        if confirmation_found and not contradiction_found:
            current_source_score += 40 # Max 40 points
            confirming_sources += 1
            if len(supporting_snippets_for_response) < 3:
                supporting_snippets_for_response.append({"source_url": url, "snippet": result.get("snippet", "N/A")[:200] + "... (supporting)"}) # Add original snippet
        elif contradiction_found and not confirmation_found:
            current_source_score -= 40 # Max -40 points (will be used to adjust overall score)
            contradicting_sources += 1
            if len(supporting_snippets_for_response) < 3:
                 supporting_snippets_for_response.append({"source_url": url, "snippet": result.get("snippet", "N/A")[:200] + "... (contradicting)"}) # Add original snippet
        elif confirmation_found and contradiction_found:
            current_source_score += 0 # Ambiguous
            if len(supporting_snippets_for_response) < 3:
                supporting_snippets_for_response.append({"source_url": url, "snippet": result.get("snippet", "N/A")[:200] + "... (ambiguous)"}) # Add original snippet
        else:
            current_source_score += 5 # Neutral or not explicitly addressing, small positive bias for relevance

        # 3. Domain Reputation (Basic)
        domain_score = 0
        if any(rep_kw in url for rep_kw in REPUTABLE_DOMAINS_KEYWORDS):
            domain_score = 20 # Max 20 points
        elif any(less_rep_kw in url for less_rep_kw in LESS_REPUTABLE_KEYWORDS):
            domain_score = -10
        current_source_score += domain_score
        
        # Max 10 points for snippet relevance if not strongly confirming/contradicting
        if not confirmation_found and not contradiction_found and matched_keywords_snippet > 0.5:
            current_source_score += 10

        total_score += current_source_score
        max_possible_score += max_source_score

    if sources_analyzed == 0:
        return {
            "is_true": None,
            "confidence_score": 0,
            "reasoning": "No valid sources found or content could not be retrieved to analyze the statement.",
            "supporting_snippets": []
        }

    # Calculate overall confidence
    # Normalize score: if total_score could be negative, adjust base or scale
    # Let's ensure score is between 0 and 100 for confidence
    # Average score per source, then scale to 0-100
    average_source_score = (total_score / sources_analyzed)
    
    # Heuristic scaling: Max score per source is ~100 (30+40+20+10). Min can be negative.
    # Let's map it to a 0-100 confidence. If average is 50, confidence is 50.
    # If average is 100, confidence 100. If average is 0, confidence 0.
    # If average is negative, confidence 0.
    confidence_score = max(0, min(100, int(average_source_score))) 

    is_true_val = None
    reasoning = f"Analyzed {sources_analyzed} source(s). "

    if confirming_sources > contradicting_sources and confidence_score > 50:
        is_true_val = True
        reasoning += f"{confirming_sources} source(s) appear to support the statement. "
        if contradicting_sources > 0:
            reasoning += f"{contradicting_sources} source(s) offer some contradictory points. "
    elif contradicting_sources > confirming_sources and confidence_score > 50: # Confidence in falsehood
        is_true_val = False
        reasoning += f"{contradicting_sources} source(s) appear to contradict the statement. "
        if confirming_sources > 0:
            reasoning += f"{confirming_sources} source(s) offer some supporting points. "
    elif confidence_score < 30:
        is_true_val = None
        reasoning += "The evidence is too weak or mixed to draw a firm conclusion. Low confidence."
    else: # Mid-confidence or mixed results
        is_true_val = None # Inconclusive
        reasoning += "Evidence is mixed or not strong enough for a definitive True/False. "
        if confirming_sources > 0:
            reasoning += f"{confirming_sources} supporting, "
        if contradicting_sources > 0:
            reasoning += f"{contradicting_sources} contradicting. "

    # Adjust confidence based on source agreement
    if sources_analyzed > 1:
        agreement_ratio = abs(confirming_sources - contradicting_sources) / sources_analyzed
        if agreement_ratio < 0.3 and confidence_score > 40: # Low agreement among sources
            confidence_score = max(20, confidence_score - 20) # Reduce confidence if sources disagree significantly
            reasoning += "Reduced confidence due to disagreement among sources. "
        elif agreement_ratio > 0.7 and confidence_score < 80: # High agreement
             confidence_score = min(100, confidence_score + 10)
             reasoning += "Increased confidence due to agreement among sources. "

    # Final check for True/False based on adjusted confidence
    if is_true_val is True and confidence_score < 40:
        is_true_val = None # Not confident enough for True
        reasoning += "Confidence too low to confirm as True. "
    elif is_true_val is False and confidence_score < 40:
        is_true_val = None # Not confident enough for False
        reasoning += "Confidence too low to confirm as False. "

    return {
        "is_true": is_true_val,
        "confidence_score": int(confidence_score),
        "reasoning": reasoning.strip(),
        "supporting_snippets": supporting_snippets_for_response
    }

# Example usage (for testing purposes)
async def main_test():
    test_statement = "The Eiffel Tower is in Paris."
    # Mock search results and content for testing
    mock_search_results = [
        {"title": "Eiffel Tower - Wikipedia", "link": "https://en.wikipedia.org/wiki/Eiffel_Tower", "snippet": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France."},
        {"title": "Is the Eiffel Tower in Berlin? - travelblog", "link": "https://example.com/blog/eiffel_berlin", "snippet": "Some people ask if the Eiffel Tower is in Berlin. This is false. It is famously in Paris."}
    ]
    mock_retrieved_contents = [
        {"url": "https://en.wikipedia.org/wiki/Eiffel_Tower", "content": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. It is named after the engineer Gustave Eiffel, whose company designed and built the tower. This is true and confirmed by many sources."},
        {"url": "https://example.com/blog/eiffel_berlin", "content": "It is a common misconception or a trick question. The Eiffel Tower is not in Berlin. That statement is false. It is located in Paris, France."}
    ]

    print(f"Analyzing statement: {test_statement}")
    analysis_result = await analyze_content_for_statement(test_statement, mock_search_results, mock_retrieved_contents)
    print(f"Result: {analysis_result}")

    test_statement_2 = "The moon is made of green cheese."
    mock_search_results_2 = [
        {"title": "Moon Composition - NASA", "link": "https://www.nasa.gov/moon-composition", "snippet": "The Moon is primarily composed of rock and minerals, not cheese. The idea of it being green cheese is a myth."},
        {"title": "Is the moon green cheese? - childrensfunfacts", "link": "https://example.com/funfacts/mooncheese", "snippet": "No, the moon is not made of green cheese! That is incorrect."}
    ]
    mock_retrieved_contents_2 = [
        {"url": "https://www.nasa.gov/moon-composition", "content": "Scientific analysis shows the Moon's composition is similar to Earth's mantle. The green cheese theory is false and has no evidence."},
        {"url": "https://example.com/funfacts/mooncheese", "content": "The story that the moon is made of green cheese is just a funny tale. It is not true. Scientists have debunked this myth."}
    ]
    print(f"\nAnalyzing statement: {test_statement_2}")
    analysis_result_2 = await analyze_content_for_statement(test_statement_2, mock_search_results_2, mock_retrieved_contents_2)
    print(f"Result: {analysis_result_2}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main_test())

