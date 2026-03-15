"""
MIRS — LLM Prompt Templates
llm/prompts.py

Prompt templates for Claude API synthesis.
Each prompt receives structured data from PubMed + Google Trends
and generates a specific section of the intelligence report.

Author: Michele De Pierri — Phase 5
"""


SYSTEM_PROMPT = """\
You are a medical intelligence analyst specializing in evidence-based medicine.
You produce concise, rigorous, and clinically relevant synthesis reports
for cardiothoracic surgeons and medical researchers.

Your output must be:
- Written in clear, professional English
- Evidence-based with specific references to the data provided
- Structured with clear sections and logical flow
- Clinically actionable where appropriate
- Honest about limitations in the available evidence

Format your response in Markdown with headers (##), bullet points, and bold
for emphasis. Do not invent data — use only what is provided in the context.
"""


def build_synthesis_prompt(
    topic: str,
    articles: list,
    evidence_score: int | None = None,
    trends_data: dict | None = None,
) -> str:
    """
    Build the user prompt for a complete synthesis report.

    Args:
        topic: The clinical topic being analyzed
        articles: List of article dicts with title, abstract, journal,
                  pub_date, article_types, authors, citations
        evidence_score: Evidence Strength Score (0-100) if available
        trends_data: Google Trends data dict if available

    Returns:
        Formatted prompt string for Claude API
    """
    # Build article summaries — include only the most relevant info
    # Limit to top 30 articles to stay within context limits
    included = [a for a in articles if a.get("included", True)]
    top_articles = included[:30]

    article_block = _format_articles(top_articles)
    stats_block = _format_statistics(included, evidence_score)
    trends_block = _format_trends(trends_data) if trends_data else ""

    prompt = f"""\
# Medical Intelligence Analysis Request

## Topic
**{topic}**

## Available Evidence Data

### Literature Statistics
{stats_block}

### Article Database ({len(top_articles)} most relevant of {len(included)} total)
{article_block}
{trends_block}

---

## Requested Analysis

Based EXCLUSIVELY on the data provided above, generate a medical intelligence
synthesis with the following three sections:

### Section 1: Key Findings
Analyze the available literature and identify:
- The **main findings** from the most cited/recent high-quality studies
- The **dominant study types** and what this implies about the maturity of evidence
- **Temporal trends** in publication volume — is research increasing or declining?
- The **leading journals and research groups** publishing on this topic
- Any notable **geographic patterns** in research activity

### Section 2: Consensus & Controversies
Based on the abstracts and study types available:
- Identify **areas of consensus** where the evidence converges
- Highlight **active controversies** or conflicting findings
- Note areas where **evidence is lacking** or of low quality
- Identify **emerging trends** that may shift current understanding
- Flag any **discrepancies** between guideline recommendations and recent evidence

### Section 3: Gap Analysis & Strategic Intelligence
Cross-reference the scientific evidence with the Google Trends data (if available)
to produce actionable intelligence:
- **Under-studied areas**: sub-topics with growing public interest (from Trends)
  but limited scientific evidence — potential research opportunities
- **Communication gaps**: areas where strong evidence exists but public awareness
  appears low — opportunities for dissemination and education
- **Emerging signals**: rising search trends or related queries that may indicate
  new clinical needs or patient concerns not yet addressed by literature
- **Research questions**: formulate 3-5 specific, testable research questions
  that emerge from the identified gaps between evidence and public interest
- **Strategic recommendations**: brief, actionable suggestions for clinicians
  and researchers based on the overall analysis

If Google Trends data is not available, base the gap analysis solely on the
evidence landscape: identify where study types are insufficient (e.g., many
case reports but no RCTs), where findings are contradictory, and what the
most impactful next studies would be.

**Important:** If the abstracts are insufficient to make specific clinical
conclusions, state this clearly rather than speculating. Reference specific
articles by their PMID when making claims.
"""
    return prompt


def _format_articles(articles: list) -> str:
    """Format articles into a compact text block for the prompt."""
    if not articles:
        return "No articles available."

    lines = []
    for i, art in enumerate(articles, 1):
        pmid = art.get("pmid", "N/A")
        title = art.get("title", "Untitled")
        journal = art.get("journal", "Unknown")
        year = str(art.get("pub_date", ""))[:4] or "N/A"
        types = ", ".join(art.get("article_types", [])) or "Article"
        citations = art.get("citations", "")
        cit_str = f" | Citations: {citations}" if citations else ""

        # First author
        authors = art.get("authors", [])
        first_author = authors[0] if authors else "Unknown"

        abstract = art.get("abstract", "")
        if abstract and len(abstract) > 500:
            abstract = abstract[:500] + "..."

        lines.append(
            f"**[{i}] PMID {pmid}** — {year} | {journal} | {types}{cit_str}\n"
            f"  *{first_author} et al.*\n"
            f"  **{title}**\n"
            f"  {abstract}\n"
        )

    return "\n".join(lines)


def _format_statistics(articles: list, evidence_score: int | None) -> str:
    """Format aggregate statistics block."""
    total = len(articles)
    if total == 0:
        return "No articles available for analysis."

    from collections import Counter

    type_counts = Counter()
    year_counts = Counter()
    journal_counts = Counter()

    for art in articles:
        for t in art.get("article_types", []):
            type_counts[t] += 1
        year_str = str(art.get("pub_date", ""))[:4]
        if year_str.isdigit():
            year_counts[int(year_str)] += 1
        j = art.get("journal", "")
        if j:
            journal_counts[j] += 1

    years = sorted(year_counts.keys()) if year_counts else []
    year_range = f"{years[0]}–{years[-1]}" if years else "N/A"
    top_journals = journal_counts.most_common(5)

    lines = [
        f"- Total articles: {total}",
        f"- Year range: {year_range}",
    ]

    if evidence_score is not None:
        lines.append(f"- Evidence Strength Score: {evidence_score}/100")

    if type_counts:
        type_str = ", ".join(f"{t}: {c}" for t, c in type_counts.most_common())
        lines.append(f"- Study types: {type_str}")

    if top_journals:
        journal_str = ", ".join(f"{j} ({c})" for j, c in top_journals)
        lines.append(f"- Top journals: {journal_str}")

    return "\n".join(lines)


def _format_trends(trends_data: dict) -> str:
    """Format Google Trends data block."""
    if not trends_data:
        return ""

    direction = trends_data.get("trend_direction", "stable")
    slope = trends_data.get("trend_slope", 0)
    peak = trends_data.get("peak_value", "N/A")
    peak_date = trends_data.get("peak_date", "N/A")
    current = trends_data.get("current_value", "N/A")
    points = trends_data.get("data_points_count", 0)

    if points == 0:
        return ""

    # Related queries
    related_top = trends_data.get("related_queries_top", [])
    top_queries_str = ""
    if related_top:
        top_5 = related_top[:5]
        top_queries_str = ", ".join(q["query"] for q in top_5)

    lines = [
        "\n### Google Trends Data",
        f"- Trend direction: {direction} (slope: {slope:+.3f}/week)",
        f"- Peak interest: {peak}/100 on {peak_date}",
        f"- Current interest: {current}/100",
        f"- Data points: {points}",
    ]

    if top_queries_str:
        lines.append(f"- Top related queries: {top_queries_str}")

    return "\n".join(lines)
