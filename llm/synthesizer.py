"""
MIRS — LLM Synthesizer
llm/synthesizer.py

Calls the Anthropic Claude API to generate narrative intelligence
synthesis from PubMed articles and Google Trends data.

Author: Michele De Pierri — Phase 5
"""

from __future__ import annotations
from typing import Optional

from llm.prompts import SYSTEM_PROMPT, build_synthesis_prompt


def synthesize_report(
    topic: str,
    articles: list,
    evidence_score: Optional[int] = None,
    trends_data: Optional[dict] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    """
    Generate an AI synthesis report using Claude API.

    Args:
        topic: Clinical topic being analyzed
        articles: List of article dicts from PubMed
        evidence_score: Evidence Strength Score (0-100)
        trends_data: Google Trends data dict
        api_key: Anthropic API key (falls back to config if None)
        model: Claude model to use (falls back to config if None)
        max_tokens: Max response tokens

    Returns:
        Markdown-formatted synthesis text

    Raises:
        ValueError: If no API key is configured
        Exception: If API call fails
    """
    # Resolve API key
    if not api_key:
        import config
        api_key = config.ANTHROPIC_API_KEY

    if not api_key:
        raise ValueError(
            "Anthropic API key not configured.\n\n"
            "Please add your key via File → Settings or in .env:\n"
            "ANTHROPIC_API_KEY=sk-ant-..."
        )

    # Resolve model
    if not model:
        try:
            import config
            model = config.LLM_MODEL
        except AttributeError:
            model = "claude-sonnet-4-20250514"

    # Build prompt
    user_prompt = build_synthesis_prompt(
        topic=topic,
        articles=articles,
        evidence_score=evidence_score,
        trends_data=trends_data,
    )

    # Call Claude API
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    # Extract text from response
    result_text = ""
    for block in message.content:
        if block.type == "text":
            result_text += block.text

    return result_text


# ── Standalone test ─────────────────────────────────────────────────── #

if __name__ == "__main__":
    test_articles = [
        {
            "pmid": "12345678",
            "title": "Outcomes of minimally invasive aortic valve replacement",
            "abstract": "Background: MIAVR has gained popularity. Methods: Retrospective analysis of 500 patients. Results: Lower mortality (1.2% vs 3.4%), shorter ICU stay.",
            "journal": "J Thorac Cardiovasc Surg",
            "pub_date": "2024",
            "article_types": ["Journal Article"],
            "authors": ["Smith J", "Doe A"],
            "included": True,
        },
    ]

    try:
        result = synthesize_report(
            topic="minimally invasive aortic valve replacement",
            articles=test_articles,
            evidence_score=65,
        )
        print(result)
    except ValueError as e:
        print(f"Config error: {e}")
    except Exception as e:
        print(f"API error: {e}")
