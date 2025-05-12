# /home/ubuntu/fact_checker_backend/src/routes/verify_api.py

import asyncio
from flask import Blueprint, request, jsonify
from src.services.search_service import perform_web_search
from src.services.content_retrieval_service import retrieve_content_from_url
from src.services.analysis_service import analyze_content_for_statement

verify_bp = Blueprint("verify_bp", __name__)

@verify_bp.route("/verify", methods=["POST"])
async def verify_statement_route():
    data = request.get_json()
    if not data or "statement" not in data:
        return jsonify({"error": "Missing statement in request body"}), 400

    statement = data["statement"]
    if not isinstance(statement, str) or not statement.strip():
        return jsonify({"error": "Statement must be a non-empty string"}), 400

    try:
        # 1. Perform Web Search
        search_results = await perform_web_search(statement, num_results=3) # Limit to 3 results for now
        if not search_results or (len(search_results) == 1 and search_results[0]["title"] == "Error"):
            return jsonify({
                "is_true": None,
                "confidence_score": 0,
                "reasoning": "Failed to perform web search or no results found.",
                "supporting_snippets": []
            }), 200 # Return 200 as the request was processed, but search failed

        # 2. Retrieve Content from URLs
        retrieval_tasks = []
        valid_search_results_for_content = []
        for res in search_results:
            if res.get("link") and res["link"] != "N/A":
                retrieval_tasks.append(retrieve_content_from_url(res["link"]))
                valid_search_results_for_content.append(res)
            else:
                # If a search result has no valid link, we can't retrieve content for it.
                print(f"Skipping content retrieval for result with no link: {res.get('title')}")

        # Run content retrieval tasks concurrently
        retrieved_contents_raw = await asyncio.gather(*retrieval_tasks)
        
        retrieved_contents_for_analysis = []
        for i, content_text in enumerate(retrieved_contents_raw):
            retrieved_contents_for_analysis.append({
                "url": valid_search_results_for_content[i]["link"],
                "content": content_text
            })

        # 3. Analyze Content
        analysis_result = await analyze_content_for_statement(statement, valid_search_results_for_content, retrieved_contents_for_analysis)

        return jsonify({
            "is_true": analysis_result.get("is_true"),
            "confidence_score": analysis_result.get("confidence_score"),
            "reasoning": analysis_result.get("reasoning", "Analysis completed."),
            "supporting_snippets": analysis_result.get("supporting_snippets", [])
        }), 200

    except Exception as e:
        print(f"Error in /verify endpoint: {e}")
        # Log the full traceback for debugging
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

