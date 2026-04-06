"""
MIRS — RIS Exporter
report/ris_exporter.py

Exports article data to RIS (Research Information Systems) format,
compatible with Zotero, Mendeley, EndNote, and other reference managers.

RIS specification: https://en.wikipedia.org/wiki/RIS_(file_format)

Author: Michele Danilo Pierri — Streamlit Phase
"""

from __future__ import annotations

import json
from typing import Optional


def export_articles_ris(
    output_path: str,
    articles: list,
    include_abstracts: bool = True,
    include_excluded: bool = False,
) -> str:
    """
    Export articles to RIS file.

    Args:
        output_path: Destination .ris file path
        articles: List of article dicts from PubMed
        include_abstracts: Whether to include abstracts
        include_excluded: Whether to include excluded articles

    Returns:
        The output_path on success.
    """
    if not include_excluded:
        articles = [a for a in articles if a.get("included", True)]

    lines = []

    for art in articles:
        # --- Parse fields ---
        authors = art.get("authors", [])
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except (json.JSONDecodeError, TypeError):
                authors = [authors] if authors else []

        article_types = art.get("article_types", [])
        if isinstance(article_types, str):
            try:
                article_types = json.loads(article_types)
            except (json.JSONDecodeError, TypeError):
                article_types = [article_types] if article_types else []

        pub_date = str(art.get("pub_date", "") or "")
        year = pub_date[:4] if len(pub_date) >= 4 else ""

        # --- Determine RIS type ---
        ris_type = _classify_ris_type(article_types)

        # --- Build RIS record ---
        lines.append(f"TY  - {ris_type}")
        lines.append(f"TI  - {art.get('title', '')}")

        for author in authors:
            if author and author.strip():
                lines.append(f"AU  - {author.strip()}")

        lines.append(f"JO  - {art.get('journal', '')}")

        if year:
            lines.append(f"PY  - {year}")
            # DA field with more detail if available
            if len(pub_date) >= 7:
                # Convert 2023-05-15 to 2023/05/15
                da = pub_date.replace("-", "/")
                lines.append(f"DA  - {da}")

        if art.get("doi"):
            lines.append(f"DO  - {art['doi']}")
            lines.append(f"UR  - https://doi.org/{art['doi']}")

        pmid = art.get("pmid", "")
        if pmid:
            lines.append(f"AN  - {pmid}")
            lines.append(f"UR  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            lines.append(f"L2  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

        lines.append("DB  - PubMed")

        # Keywords from article types
        for at in article_types:
            if at and at.strip():
                lines.append(f"KW  - {at.strip()}")

        if include_abstracts:
            abstract = art.get("abstract", "")
            if abstract:
                # RIS spec: AB field, single line
                clean_abstract = " ".join(abstract.split())
                lines.append(f"AB  - {clean_abstract}")

        # End of record
        lines.append("ER  - ")
        lines.append("")  # blank line between records

    # Write with UTF-8 encoding
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def articles_to_ris_string(
    articles: list,
    include_abstracts: bool = True,
    include_excluded: bool = False,
) -> str:
    """
    Generate RIS content as a string (for Streamlit download button).

    Args:
        articles: List of article dicts
        include_abstracts: Whether to include abstracts
        include_excluded: Whether to include excluded articles

    Returns:
        RIS-formatted string
    """
    if not include_excluded:
        articles = [a for a in articles if a.get("included", True)]

    lines = []

    for art in articles:
        authors = art.get("authors", [])
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except (json.JSONDecodeError, TypeError):
                authors = [authors] if authors else []

        article_types = art.get("article_types", [])
        if isinstance(article_types, str):
            try:
                article_types = json.loads(article_types)
            except (json.JSONDecodeError, TypeError):
                article_types = [article_types] if article_types else []

        pub_date = str(art.get("pub_date", "") or "")
        year = pub_date[:4] if len(pub_date) >= 4 else ""

        ris_type = _classify_ris_type(article_types)

        lines.append(f"TY  - {ris_type}")
        lines.append(f"TI  - {art.get('title', '')}")

        for author in authors:
            if author and author.strip():
                lines.append(f"AU  - {author.strip()}")

        lines.append(f"JO  - {art.get('journal', '')}")

        if year:
            lines.append(f"PY  - {year}")
            if len(pub_date) >= 7:
                da = pub_date.replace("-", "/")
                lines.append(f"DA  - {da}")

        if art.get("doi"):
            lines.append(f"DO  - {art['doi']}")
            lines.append(f"UR  - https://doi.org/{art['doi']}")

        pmid = art.get("pmid", "")
        if pmid:
            lines.append(f"AN  - {pmid}")
            lines.append(f"UR  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
            lines.append(f"L2  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

        lines.append("DB  - PubMed")

        for at in article_types:
            if at and at.strip():
                lines.append(f"KW  - {at.strip()}")

        if include_abstracts:
            abstract = art.get("abstract", "")
            if abstract:
                clean_abstract = " ".join(abstract.split())
                lines.append(f"AB  - {clean_abstract}")

        lines.append("ER  - ")
        lines.append("")

    return "\n".join(lines)


def _classify_ris_type(article_types: list) -> str:
    """
    Map PubMed article types to RIS type tags.

    RIS types used:
        JOUR  — Journal Article (default)
        CTRIAL — Clinical Trial (mapped to JOUR since no specific RIS type)
        MGZN  — Magazine article
        RPRT  — Report
        CHAP  — Book chapter
    """
    if not article_types:
        return "JOUR"

    types_lower = " ".join(str(t) for t in article_types).lower()

    if "review" in types_lower or "meta-analysis" in types_lower:
        return "JOUR"
    if "guideline" in types_lower:
        return "JOUR"
    if "case report" in types_lower:
        return "JOUR"
    if "letter" in types_lower or "editorial" in types_lower:
        return "JOUR"
    if "book" in types_lower:
        return "CHAP"

    return "JOUR"
