"""
MIRS — PDF Report Generator
report/pdf_generator.py

Generates a professional, print-friendly PDF report using fpdf2.

Theme: LIGHT (white background, dark text) — optimised for printing.
Cover page only uses dark theme for visual impact.

Sections:
  1. Cover page (dark) with title, topic, date, article count
  2. Executive Summary — stat cards
  3. Article Table — PMID, Year, Title, Authors, Journal, Type
  4. AI Synthesis — rendered Markdown text

Dependencies: fpdf2 (only)
Author: Michele De Pierri — Phase 7
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from fpdf import FPDF


# ── Colour palette — LIGHT THEME (print-friendly) ────────────────────── #

class C:
    WHITE = (255, 255, 255)
    TEXT_PRIMARY = (30, 30, 50)
    TEXT_SECONDARY = (100, 110, 130)
    ACCENT_BLUE = (44, 95, 138)
    ACCENT_LIGHT_BLUE = (70, 130, 180)
    HEADER_BG = (26, 26, 58)
    COVER_TEXT = (240, 240, 255)
    TABLE_HEADER_BG = (44, 95, 138)
    TABLE_HEADER_TEXT = (255, 255, 255)
    TABLE_ROW_EVEN = (245, 247, 250)
    TABLE_ROW_ODD = (255, 255, 255)
    TABLE_BORDER = (210, 215, 225)
    STAT_CARD_BG = (240, 244, 250)
    STAT_CARD_BORDER = (200, 210, 225)
    SCORE_GREEN = (46, 139, 87)
    SCORE_YELLOW = (200, 150, 30)
    SCORE_RED = (200, 60, 60)
    HR = (200, 210, 225)


def _score_colour(score: Optional[float]) -> tuple:
    if score is None:
        return C.TEXT_SECONDARY
    if score >= 70:
        return C.SCORE_GREEN
    if score >= 40:
        return C.SCORE_YELLOW
    return C.SCORE_RED


def _safe(text: str, max_len: int = 0) -> str:
    if not text:
        return ""
    text = text.replace("\u2009", " ").replace("\u00a0", " ")
    text = text.replace("\u2013", "-").replace("\u2014", "--")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2026", "...")
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    if max_len > 0 and len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def _first_author(authors) -> str:
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except (json.JSONDecodeError, TypeError):
            return _safe(authors, 30)
    if isinstance(authors, list) and authors:
        first = authors[0]
        if len(authors) > 1:
            first += " et al."
        return _safe(first, 30)
    return "-"


def _extract_year(pub_date) -> str:
    if pub_date and len(str(pub_date)) >= 4:
        return str(pub_date)[:4]
    return "-"


def _format_types(article_types) -> str:
    if isinstance(article_types, str):
        try:
            article_types = json.loads(article_types)
        except (json.JSONDecodeError, TypeError):
            return _safe(article_types, 25)
    if isinstance(article_types, list) and article_types:
        abbrevs = {
            "Randomized Controlled Trial": "RCT",
            "Meta-Analysis": "Meta",
            "Systematic Review": "Syst.Rev.",
            "Clinical Trial": "CT",
            "Review": "Review",
            "Journal Article": "Article",
            "Practice Guideline": "Guideline",
            "Comparative Study": "Comp.Study",
            "Case Reports": "Case Rep.",
        }
        short = [abbrevs.get(t, t) for t in article_types[:2]]
        return _safe(", ".join(short), 25)
    return "-"


def _count_by_type(articles: list) -> dict:
    rct = meta = reviews = guidelines = 0
    for a in articles:
        types = a.get("article_types", [])
        if isinstance(types, str):
            try:
                types = json.loads(types)
            except Exception:
                types = []
        for t in types:
            tl = t.lower()
            if "randomized controlled" in tl or "clinical trial" in tl:
                rct += 1; break
            elif "meta-analysis" in tl or "systematic review" in tl:
                meta += 1; break
            elif t == "Review":
                reviews += 1; break
            elif "guideline" in tl:
                guidelines += 1; break
    return {"rct": rct, "meta": meta, "reviews": reviews, "guidelines": guidelines}


# ── Markdown parser ──────────────────────────────────────────────────── #

def _parse_markdown_to_blocks(md_text: str) -> list[dict]:
    blocks = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1; continue
        if re.match(r"^-{3,}$", stripped):
            blocks.append({"type": "hr"}); i += 1; continue
        m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m:
            blocks.append({"type": f"h{len(m.group(1))}", "text": m.group(2)})
            i += 1; continue
        if stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:]); i += 1
            blocks.append({"type": "list", "items": items}); continue
        blocks.append({"type": "paragraph", "text": stripped}); i += 1
    return blocks


# ── FPDF subclass ────────────────────────────────────────────────────── #

class MIRSReport(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self._topic = ""

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*C.TEXT_SECONDARY)
        self.cell(0, 6, f"MIRS Report - {_safe(self._topic)}", align="L")
        self.cell(0, 6, f"Page {self.page_no() - 1}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C.HR)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        if self.page_no() <= 1:
            return
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*C.TEXT_SECONDARY)
        self.cell(0, 8, f"Generated by MIRS v7.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")


# ── Public API ────────────────────────────────────────────────────────── #

def generate_pdf_report(
    output_path: str,
    articles: list,
    topic: str = "",
    evidence_score: Optional[float] = None,
    synthesis_text: str = "",
    trends_data: Optional[dict] = None,
    include_abstracts: bool = False,
    include_excluded: bool = False,
) -> str:
    """
    Generate a complete MIRS PDF report (light theme, print-friendly).
    Cover page uses dark theme; all other pages are white.

    Args:
        output_path: Destination file path (.pdf)
        articles: List of article dicts
        topic: Query topic string
        evidence_score: Evidence Strength Score (0-100) or None
        synthesis_text: AI synthesis Markdown text (if available)
        trends_data: Accepted for interface compatibility (not used in PDF)
        include_abstracts: Whether to include abstracts in article table
        include_excluded: Whether to include excluded articles

    Returns:
        The output_path on success.
    """
    if not include_excluded:
        articles = [a for a in articles if a.get("included", True)]

    counts = _count_by_type(articles)
    n = len(articles)
    pdf = MIRSReport()
    pdf._topic = topic

    # ─── PAGE 1: Cover (dark) ─────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*C.HEADER_BG)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_y(80)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*C.COVER_TEXT)
    pdf.cell(0, 14, "MIRS", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(160, 170, 200)
    pdf.cell(0, 10, "Medical Intelligence Report System", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(100, 160, 255); pdf.set_line_width(0.5)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 18); pdf.set_text_color(*C.COVER_TEXT)
    pdf.multi_cell(0, 10, _safe(topic or "Intelligence Report"), align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11); pdf.set_text_color(160, 170, 200)
    pdf.cell(0, 7, f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"{n} articles analysed", align="C", new_x="LMARGIN", new_y="NEXT")
    if evidence_score is not None:
        pdf.ln(4); pdf.set_font("Helvetica", "B", 13)
        sc = _score_colour(evidence_score)
        pdf.set_text_color(min(sc[0]+60, 255), min(sc[1]+60, 255), min(sc[2]+60, 255))
        pdf.cell(0, 8, f"Evidence Strength Score: {evidence_score:.0f}/100", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(260); pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(160, 170, 200)
    pdf.cell(0, 6, "Developer: Michele De Pierri", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Data source: PubMed E-utilities (NCBI)", align="C", new_x="LMARGIN", new_y="NEXT")

    # ─── PAGE 2: Executive Summary (light) ────────────────────────
    pdf.add_page()
    _section_header(pdf, "Executive Summary")
    card_data = [
        ("Total Articles", str(n)),
        ("RCTs / CT", str(counts["rct"])),
        ("Meta / SR", str(counts["meta"])),
        ("Reviews", str(counts["reviews"])),
        ("Guidelines", str(counts["guidelines"])),
        ("Evidence Score", f"{evidence_score:.0f}/100" if evidence_score is not None else "-"),
    ]
    _draw_stat_cards(pdf, card_data, evidence_score)

    years = []
    for a in articles:
        y = _extract_year(a.get("pub_date", ""))
        if y != "-":
            try: years.append(int(y))
            except ValueError: pass
    if years:
        pdf.ln(4); pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*C.TEXT_SECONDARY)
        pdf.cell(0, 6, f"Publication range: {min(years)} - {max(years)}", align="C", new_x="LMARGIN", new_y="NEXT")

    # ─── Article Table (light) ────────────────────────────────────
    pdf.add_page()
    _section_header(pdf, "Article List")
    _draw_article_table(pdf, articles, include_abstracts)

    # ─── AI Synthesis (light) ─────────────────────────────────────
    if synthesis_text and synthesis_text.strip():
        pdf.add_page()
        _section_header(pdf, "AI Synthesis & Gap Analysis")
        blocks = _parse_markdown_to_blocks(synthesis_text)
        _render_markdown_blocks(pdf, blocks)

    # ─── Write ────────────────────────────────────────────────────
    pdf.output(output_path)
    return output_path


# ── Drawing helpers ───────────────────────────────────────────────────── #

def _section_header(pdf: MIRSReport, title: str):
    pdf.set_font("Helvetica", "B", 16); pdf.set_text_color(*C.ACCENT_BLUE)
    pdf.cell(0, 10, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*C.ACCENT_BLUE); pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(6)


def _draw_stat_cards(pdf: MIRSReport, card_data: list[tuple[str, str]], evidence_score: Optional[float] = None):
    card_w, card_h, gap = 58, 28, 4
    start_x = 10 + (190 - 3 * card_w - 2 * gap) / 2
    for idx, (label, value) in enumerate(card_data):
        col, row = idx % 3, idx // 3
        x = start_x + col * (card_w + gap)
        y = pdf.get_y() + row * (card_h + gap)
        pdf.set_fill_color(*C.STAT_CARD_BG); pdf.set_draw_color(*C.STAT_CARD_BORDER)
        pdf.rect(x, y, card_w, card_h, style="DF")
        if label == "Evidence Score" and evidence_score is not None:
            pdf.set_text_color(*_score_colour(evidence_score))
        else:
            pdf.set_text_color(*C.ACCENT_BLUE)
        pdf.set_font("Helvetica", "B", 18); pdf.set_xy(x, y + 3)
        pdf.cell(card_w, 10, _safe(value), align="C")
        pdf.set_text_color(*C.TEXT_SECONDARY); pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(x, y + 15); pdf.cell(card_w, 8, _safe(label), align="C")
    total_rows = (len(card_data) + 2) // 3
    pdf.set_y(pdf.get_y() + total_rows * (card_h + gap) + 4)


def _draw_article_table(pdf: MIRSReport, articles: list, include_abstracts: bool = False):
    col_w = [18, 12, 65, 30, 38, 27]
    headers = ["PMID", "Year", "Title", "First Author", "Journal", "Type"]
    row_h = 7

    def _table_header():
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(*C.TABLE_HEADER_BG); pdf.set_text_color(*C.TABLE_HEADER_TEXT)
        pdf.set_draw_color(*C.TABLE_BORDER)
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], row_h, f" {h}", border=1, fill=True)
        pdf.ln()

    _table_header()
    pdf.set_font("Helvetica", "", 6.5)

    for idx, art in enumerate(articles):
        if pdf.get_y() + row_h > 275:
            pdf.add_page(); _table_header(); pdf.set_font("Helvetica", "", 6.5)
        pdf.set_fill_color(*(C.TABLE_ROW_EVEN if idx % 2 == 0 else C.TABLE_ROW_ODD))
        pdf.set_text_color(*(C.TEXT_PRIMARY if art.get("included", True) else (170, 170, 170)))
        pdf.set_draw_color(*C.TABLE_BORDER)
        row_data = [
            _safe(art.get("pmid", ""), 12), _extract_year(art.get("pub_date", "")),
            _safe(art.get("title", ""), 80), _first_author(art.get("authors", [])),
            _safe(art.get("journal", ""), 35), _format_types(art.get("article_types", [])),
        ]
        for i, val in enumerate(row_data):
            pdf.cell(col_w[i], row_h, f" {val}", border=1, fill=True)
        pdf.ln()
        if include_abstracts:
            abstract = art.get("abstract", "")
            if abstract:
                if pdf.get_y() + 12 > 275:
                    pdf.add_page(); _table_header(); pdf.set_font("Helvetica", "", 6.5)
                pdf.set_font("Helvetica", "I", 5.5); pdf.set_text_color(*C.TEXT_SECONDARY)
                pdf.multi_cell(sum(col_w), 3.5, _safe(abstract, 500), border=0)
                pdf.set_font("Helvetica", "", 6.5)

    pdf.ln(4); pdf.set_font("Helvetica", "I", 8); pdf.set_text_color(*C.TEXT_SECONDARY)
    pdf.cell(0, 6, f"Total: {len(articles)} articles", new_x="LMARGIN", new_y="NEXT")


def _render_markdown_blocks(pdf: MIRSReport, blocks: list[dict]):
    for block in blocks:
        btype = block["type"]
        if pdf.get_y() > 265:
            pdf.add_page()
        if btype == "h1":
            pdf.ln(4); pdf.set_font("Helvetica", "B", 15); pdf.set_text_color(*C.ACCENT_BLUE)
            pdf.multi_cell(0, 8, _safe(block["text"])); pdf.ln(2)
        elif btype == "h2":
            pdf.ln(3); pdf.set_font("Helvetica", "B", 12); pdf.set_text_color(*C.ACCENT_LIGHT_BLUE)
            pdf.multi_cell(0, 7, _safe(block["text"])); pdf.ln(2)
        elif btype == "h3":
            pdf.ln(2); pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(60, 75, 100)
            pdf.multi_cell(0, 6, _safe(block["text"])); pdf.ln(1)
        elif btype == "paragraph":
            pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*C.TEXT_PRIMARY)
            pdf.multi_cell(0, 5, _safe(block["text"]).replace("**", "").replace("*", "")); pdf.ln(2)
        elif btype == "list":
            pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*C.TEXT_PRIMARY)
            for item in block["items"]:
                if pdf.get_y() > 270: pdf.add_page()
                pdf.cell(6, 5, "-"); pdf.multi_cell(0, 5, _safe(item).replace("**", "").replace("*", "")); pdf.ln(1)
        elif btype == "hr":
            pdf.ln(3); pdf.set_draw_color(*C.HR); pdf.set_line_width(0.3)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(3)
