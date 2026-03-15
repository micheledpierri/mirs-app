"""
MIRS — CSV Exporter
report/csv_exporter.py

Exports article data to CSV format compatible with Excel, Google Sheets,
and other spreadsheet applications.

Uses Python's built-in csv module (no pandas dependency required).

Author: Michele De Pierri — Phase 7
"""

from __future__ import annotations

import csv
import json
from typing import Optional


def export_articles_csv(
    output_path: str,
    articles: list,
    include_abstracts: bool = True,
    include_excluded: bool = False,
) -> str:
    """
    Export articles to CSV file.

    Args:
        output_path: Destination .csv file path
        articles: List of article dicts
        include_abstracts: Whether to include the abstract column
        include_excluded: Whether to include excluded articles

    Returns:
        The output_path on success.
    """
    # Filter
    if not include_excluded:
        articles = [a for a in articles if a.get("included", True)]

    # Define columns
    columns = [
        "PMID", "Title", "Authors", "Journal", "Year",
        "Article_Types", "DOI", "Included", "User_Notes",
    ]
    if include_abstracts:
        columns.append("Abstract")

    # Write with UTF-8 BOM for proper Excel opening
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for art in articles:
            # Parse JSON fields
            authors = art.get("authors", [])
            if isinstance(authors, str):
                try:
                    authors = json.loads(authors)
                except (json.JSONDecodeError, TypeError):
                    authors = [authors]

            article_types = art.get("article_types", [])
            if isinstance(article_types, str):
                try:
                    article_types = json.loads(article_types)
                except (json.JSONDecodeError, TypeError):
                    article_types = [article_types]

            pub_date = art.get("pub_date", "")
            year = str(pub_date)[:4] if pub_date and len(str(pub_date)) >= 4 else ""

            row = {
                "PMID": art.get("pmid", ""),
                "Title": art.get("title", ""),
                "Authors": "; ".join(authors) if isinstance(authors, list) else str(authors),
                "Journal": art.get("journal", ""),
                "Year": year,
                "Article_Types": "; ".join(article_types) if isinstance(article_types, list) else str(article_types),
                "DOI": art.get("doi", "") or "",
                "Included": "Yes" if art.get("included", True) else "No",
                "User_Notes": art.get("user_notes", "") or "",
            }
            if include_abstracts:
                row["Abstract"] = art.get("abstract", "") or ""

            writer.writerow(row)

    return output_path
