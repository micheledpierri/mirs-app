"""
MIRS — Interactive Plotly Charts Generator
report/charts.py

Generates interactive Plotly charts as standalone HTML loaded
into QWebEngineView in the Charts tab of the center panel.

Charts implemented:
  1. publication_trend()      — Stacked bar chart per year, colored by study type
  2. evidence_pyramid()       — Donut chart by evidence level
  3. journal_distribution()   — Top N journals by publication volume
  4. generate_dashboard_html() — Full HTML dashboard with all 3 charts

Author: Michele De Pierri — Phase 3
"""

from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional


# ── Configurazione colori (dark theme coerente con MIRS) ────────────── #

DARK_BG = "#1a1a3a"
DARK_PAPER = "#22223a"
TEXT_COLOR = "#e0e0f0"
GRID_COLOR = "#2a2a5a"
AXIS_COLOR = "#6060a0"

# Colori per tipo di studio (ordinati per livello di evidenza)
STUDY_COLORS = {
    "Meta-Analysis":                "#ff6b6b",   # rosso — apice piramide
    "Systematic Review":            "#ff9f43",   # arancio
    "Randomized Controlled Trial":  "#feca57",   # giallo
    "Clinical Trial":               "#48dbfb",   # azzurro
    "Practice Guideline":           "#ff9ff3",   # magenta
    "Review":                       "#54a0ff",   # blu
    "Comparative Study":            "#5f27cd",   # viola
    "Case Reports":                 "#00d2d3",   # teal
    "Journal Article":              "#576574",   # grigio
    "Other":                        "#3d3d5a",   # grigio scuro
}

# Mapping per la piramide delle evidenze (livello 1 = più alto)
EVIDENCE_HIERARCHY = {
    "Meta-Analysis":               1,
    "Systematic Review":           2,
    "Randomized Controlled Trial": 3,
    "Clinical Trial":              4,
    "Practice Guideline":          5,
    "Review":                      6,
    "Comparative Study":           7,
    "Case Reports":                8,
    "Journal Article":             9,
    "Other":                       10,
}

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"


# ── Funzioni di normalizzazione dati ────────────────────────────────── #

def _get_field(article, field: str, default=""):
    """Accesso uniforme a campi su dict o oggetti SQLAlchemy."""
    if isinstance(article, dict):
        return article.get(field, default) or default
    return getattr(article, field, default) or default


def _classify_article_type(article_types_input) -> str:
    """
    Classifica un articolo nella categoria di studio più specifica disponibile.
    Ordine di priorità: Meta-Analysis > Systematic Review > RCT > ...

    Accetta sia una stringa che una lista di stringhe.
    """
    if article_types_input is None:
        return "Other"
    if isinstance(article_types_input, list):
        article_types_str = " ".join(article_types_input)
    else:
        article_types_str = str(article_types_input)

    at_lower = article_types_str.lower()

    if "meta-analysis" in at_lower or "meta analysis" in at_lower:
        return "Meta-Analysis"
    if "systematic review" in at_lower:
        return "Systematic Review"
    if "randomized controlled trial" in at_lower or "randomised controlled" in at_lower:
        return "Randomized Controlled Trial"
    if "clinical trial" in at_lower:
        return "Clinical Trial"
    if "practice guideline" in at_lower or "guideline" in at_lower:
        return "Practice Guideline"
    if "review" in at_lower:
        return "Review"
    if "comparative study" in at_lower:
        return "Comparative Study"
    if "case report" in at_lower:
        return "Case Reports"
    if "journal article" in at_lower:
        return "Journal Article"
    return "Other"


def _extract_year(pub_date) -> Optional[int]:
    """Estrae l'anno da pub_date in formato stringa o int."""
    if pub_date is None:
        return None
    try:
        year = int(str(pub_date)[:4])
        if 1900 <= year <= datetime.now().year + 1:
            return year
    except (ValueError, TypeError):
        pass
    return None


def _plotly_config() -> dict:
    """Config Plotly comune: toolbar minimale, responsive, dark."""
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "select2d", "lasso2d", "autoScale2d",
            "hoverClosestCartesian", "hoverCompareCartesian"
        ],
        "responsive": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "mirs_chart",
            "scale": 2
        }
    }


def _dark_layout(title: str, extra: Optional[dict] = None) -> dict:
    """Layout Plotly comune con dark theme MIRS."""
    layout = {
        "title": {
            "text": title,
            "font": {"size": 16, "color": TEXT_COLOR, "family": "Arial"},
            "x": 0.02
        },
        "paper_bgcolor": DARK_PAPER,
        "plot_bgcolor": DARK_BG,
        "font": {"color": TEXT_COLOR, "family": "Arial"},
        "legend": {
            "bgcolor": DARK_PAPER,
            "bordercolor": GRID_COLOR,
            "borderwidth": 1,
            "font": {"color": TEXT_COLOR, "size": 11}
        },
        "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
        "hoverlabel": {
            "bgcolor": "#2a2a5a",
            "font": {"color": "#ffffff", "size": 12}
        }
    }
    if extra:
        layout.update(extra)
    return layout


# ── Chart 1: Publication Trend ─────────────────────────────────────── #

def publication_trend(articles: list, title: str = "Publication Trend") -> str:
    """
    Generate a stacked bar chart per year, colored by study type.

    Returns:
        HTML string of the Plotly div (to embed in the page).
    """
    year_type_count: dict[int, Counter] = defaultdict(Counter)
    for art in articles:
        year = _extract_year(_get_field(art, "pub_date"))
        art_type = _classify_article_type(_get_field(art, "article_types"))
        if year is not None:
            year_type_count[year][art_type] += 1

    if not year_type_count:
        return _empty_chart_html("No data available for Publication Trend")

    years = sorted(year_type_count.keys())

    all_types_present = set()
    for counts in year_type_count.values():
        all_types_present.update(counts.keys())

    type_order = [t for t in EVIDENCE_HIERARCHY if t in all_types_present]
    for t in all_types_present:
        if t not in type_order:
            type_order.append(t)

    traces = []
    for study_type in type_order:
        y_values = [year_type_count[yr].get(study_type, 0) for yr in years]
        if sum(y_values) == 0:
            continue
        color = STUDY_COLORS.get(study_type, "#888888")
        traces.append({
            "type": "bar",
            "name": study_type,
            "x": years,
            "y": y_values,
            "marker": {"color": color},
            "hovertemplate": f"<b>{study_type}</b><br>Year: %{{x}}<br>Articles: %{{y}}<extra></extra>"
        })

    # Add invisible trace for total annotations on top of each bar
    year_totals = [sum(year_type_count[yr].values()) for yr in years]
    traces.append({
        "type": "scatter",
        "x": years,
        "y": year_totals,
        "mode": "text",
        "text": [str(t) for t in year_totals],
        "textposition": "top center",
        "textfont": {"color": TEXT_COLOR, "size": 11},
        "showlegend": False,
        "hoverinfo": "skip"
    })

    layout = _dark_layout(title, {
        "barmode": "stack",
        "xaxis": {
            "title": "Year",
            "tickmode": "array",
            "tickvals": years,
            "ticktext": [str(y) for y in years],
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR
        },
        "yaxis": {
            "title": "Number of articles",
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR
        },
        "height": 380,
        "margin": {"l": 60, "r": 20, "t": 60, "b": 60}
    })

    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "publication_trend_chart")


# ── Chart 2: Evidence Pyramid ──────────────────────────────────────── #

def evidence_pyramid(articles: list, title: str = "Evidence Pyramid") -> str:
    """
    Donut chart showing the distribution of articles by evidence level.

    Returns:
        HTML string of the Plotly div.
    """
    type_counts: Counter = Counter()
    for art in articles:
        art_type = _classify_article_type(_get_field(art, "article_types"))
        type_counts[art_type] += 1

    if not type_counts:
        return _empty_chart_html("No data available for Evidence Pyramid")

    sorted_types = sorted(
        type_counts.keys(),
        key=lambda t: EVIDENCE_HIERARCHY.get(t, 99)
    )

    labels = sorted_types
    values = [type_counts[t] for t in sorted_types]
    colors = [STUDY_COLORS.get(t, "#888888") for t in sorted_types]

    # Build enriched labels with article counts for the legend
    enriched_labels = [f"{t}  ({type_counts[t]})" for t in sorted_types]

    traces = [{
        "type": "pie",
        "labels": enriched_labels,
        "values": values,
        "marker": {
            "colors": colors,
            "line": {"color": DARK_BG, "width": 2}
        },
        "textinfo": "percent",
        "textposition": "inside",
        "insidetextorientation": "radial",
        "textfont": {"size": 12, "color": "#ffffff"},
        "hovertemplate": "<b>%{label}</b><br>Articles: %{value}<br>%{percent}<extra></extra>",
        "hole": 0.38,
        "sort": False,
        "automargin": True
    }]

    layout = _dark_layout(title, {
        "showlegend": True,
        "legend": {
            "orientation": "h",
            "x": 0.5,
            "y": -0.18,
            "xanchor": "center",
            "yanchor": "top",
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "font": {"color": TEXT_COLOR, "size": 11},
            "itemsizing": "constant",
            "traceorder": "normal"
        },
        "margin": {"l": 20, "r": 20, "t": 50, "b": 120},
        "height": 420
    })

    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "evidence_pyramid_chart")


# ── Chart 3: Journal Distribution ──────────────────────────────────── #

def journal_distribution(articles: list, top_n: int = 10, title: str = "Top Journals") -> str:
    """
    Horizontal bar chart for the top N journals by article count.
    """
    journal_counts: Counter = Counter()
    for art in articles:
        journal = _get_field(art, "journal")
        if journal and journal.strip():
            journal_clean = journal.strip().title()
            journal_counts[journal_clean] += 1

    if not journal_counts:
        return _empty_chart_html("No data available for Journal Distribution")

    top_journals = journal_counts.most_common(top_n)
    journals = [j for j, _ in reversed(top_journals)]
    counts = [c for _, c in reversed(top_journals)]

    max_count = max(counts) if counts else 1
    bar_colors = [
        f"rgba(74, 110, 168, {0.4 + 0.6 * (c / max_count):.2f})"
        for c in counts
    ]

    traces = [{
        "type": "bar",
        "orientation": "h",
        "x": counts,
        "y": journals,
        "marker": {
            "color": bar_colors,
            "line": {"color": "#6080c0", "width": 0.5}
        },
        "text": [str(c) for c in counts],
        "textposition": "auto",
        "textfont": {"color": "#ffffff", "size": 12},
        "hovertemplate": "<b>%{y}</b><br>Articles: %{x}<extra></extra>",
        "cliponaxis": False
    }]

    chart_height = max(340, len(journals) * 38 + 120)

    layout = _dark_layout(title, {
        "xaxis": {
            "title": "Number of articles",
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "tickfont": {"size": 11}
        },
        "yaxis": {
            "automargin": True,
            "tickfont": {"size": 11},
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR
        },
        "showlegend": False,
        "height": chart_height,
        "margin": {"l": 20, "r": 60, "t": 50, "b": 50}
    })

    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "journal_distribution_chart")


# ── Chart 4: Google Trends Interest Over Time (Phase 4) ──────────────── #

TRENDS_LINE_COLOR = "#54a0ff"      # blue
TRENDS_FILL_COLOR = "rgba(84, 160, 255, 0.15)"

def trends_interest_timeline(
    trends_data: dict,
    articles: Optional[list] = None,
    title: str = "Google Trends — Search Interest Over Time",
) -> str:
    """
    Line chart showing Google Trends interest over time.

    Optionally overlays the publication count per year as a bar chart
    on a secondary y-axis for comparison.

    Args:
        trends_data: Dict from TrendsAgent.fetch_all()
        articles: If provided, overlays publication bars for comparison
        title: Chart title

    Returns:
        HTML string of the Plotly div.
    """
    iot = trends_data.get('interest_over_time', [])
    if not iot:
        return _empty_chart_html("No Google Trends data available")

    dates = [dp['date'] for dp in iot]
    values = [dp['value'] for dp in iot]

    traces = []

    # Primary trace: Trends interest line
    traces.append({
        "type": "scatter",
        "mode": "lines",
        "name": "Search Interest",
        "x": dates,
        "y": values,
        "line": {"color": TRENDS_LINE_COLOR, "width": 2},
        "fill": "tozeroy",
        "fillcolor": TRENDS_FILL_COLOR,
        "hovertemplate": "<b>%{x}</b><br>Interest: %{y}/100<extra></extra>",
    })

    # Optional secondary axis: publication count per year
    extra_layout = {}
    if articles:
        year_counts = Counter()
        for art in articles:
            yr = _extract_year(_get_field(art, "pub_date"))
            if yr:
                year_counts[yr] += 1

        if year_counts:
            pub_years = sorted(year_counts.keys())
            pub_counts = [year_counts[y] for y in pub_years]
            # Place bars at July 1st of each year for alignment
            pub_dates = [f"{y}-07-01" for y in pub_years]

            traces.append({
                "type": "bar",
                "name": "Publications",
                "x": pub_dates,
                "y": pub_counts,
                "yaxis": "y2",
                "marker": {"color": "rgba(255, 202, 87, 0.5)", "line": {"width": 0}},
                "width": 1000 * 60 * 60 * 24 * 120,  # ~4 months width in ms
                "hovertemplate": "<b>%{x|%Y}</b><br>Publications: %{y}<extra></extra>",
            })

            extra_layout["yaxis2"] = {
                "title": "Publications",
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "titlefont": {"color": "#feca57"},
                "tickfont": {"color": "#feca57"},
            }

    # Annotate trend direction
    direction = trends_data.get('trend_direction', 'stable')
    slope = trends_data.get('trend_slope', 0)
    direction_icon = "📈" if direction == "rising" else ("📉" if direction == "declining" else "➡️")

    extra_layout.update({
        "xaxis": {
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "type": "date",
        },
        "yaxis": {
            "title": "Search Interest (0-100)",
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "range": [0, 105],
        },
        "height": 380,
        "annotations": [{
            "text": f"{direction_icon} Trend: {direction} (slope: {slope:+.2f}/week)",
            "xref": "paper", "yref": "paper",
            "x": 1.0, "y": 1.08,
            "showarrow": False,
            "font": {"size": 12, "color": "#a0c0ff"},
            "xanchor": "right",
        }],
    })

    layout = _dark_layout(title, extra_layout)
    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "trends_interest_chart")


# ── Chart 5: Related Queries (Phase 4) ──────────────────────────────── #

def trends_related_queries(
    trends_data: dict,
    title: str = "Google Trends — Related Queries",
) -> str:
    """
    Horizontal bar chart showing the top related queries from Google Trends.

    Args:
        trends_data: Dict from TrendsAgent.fetch_all()
        title: Chart title

    Returns:
        HTML string of the Plotly div.
    """
    top_q = trends_data.get('related_queries_top', [])
    if not top_q:
        return _empty_chart_html("No related queries available")

    # Take top 15 queries
    top_q = top_q[:15]

    queries = [q['query'] for q in reversed(top_q)]
    values = [q['value'] for q in reversed(top_q)]

    max_val = max(values) if values else 1
    bar_colors = [
        f"rgba(84, 160, 255, {0.35 + 0.65 * (v / max_val):.2f})"
        for v in values
    ]

    traces = [{
        "type": "bar",
        "orientation": "h",
        "x": values,
        "y": queries,
        "marker": {
            "color": bar_colors,
            "line": {"color": TRENDS_LINE_COLOR, "width": 0.5},
        },
        "text": [str(v) for v in values],
        "textposition": "auto",
        "textfont": {"color": "#ffffff", "size": 11},
        "hovertemplate": "<b>%{y}</b><br>Relevance: %{x}/100<extra></extra>",
        "cliponaxis": False,
    }]

    chart_height = max(340, len(queries) * 32 + 120)

    layout = _dark_layout(title, {
        "xaxis": {
            "title": "Relative Interest (0-100)",
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
        },
        "yaxis": {
            "automargin": True,
            "tickfont": {"size": 11},
        },
        "showlegend": False,
        "height": chart_height,
        "margin": {"l": 20, "r": 60, "t": 50, "b": 50},
    })

    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "trends_related_queries_chart")


# ── Chart 6: Interest by Region (Phase 4) ───────────────────────────── #

def trends_region_chart(
    trends_data: dict,
    top_n: int = 20,
    title: str = "Google Trends — Interest by Region",
) -> str:
    """
    Horizontal bar chart showing interest by country/region.

    Args:
        trends_data: Dict from TrendsAgent.fetch_all()
        top_n: Number of top regions to show
        title: Chart title

    Returns:
        HTML string of the Plotly div.
    """
    regions = trends_data.get('interest_by_region', [])
    if not regions:
        return _empty_chart_html("No regional data available")

    regions = regions[:top_n]

    names = [r['region'] for r in reversed(regions)]
    values = [r['value'] for r in reversed(regions)]

    max_val = max(values) if values else 1
    bar_colors = [
        f"rgba(0, 210, 211, {0.3 + 0.7 * (v / max_val):.2f})"
        for v in values
    ]

    traces = [{
        "type": "bar",
        "orientation": "h",
        "x": values,
        "y": names,
        "marker": {
            "color": bar_colors,
            "line": {"color": "#00d2d3", "width": 0.5},
        },
        "text": [str(v) for v in values],
        "textposition": "auto",
        "textfont": {"color": "#ffffff", "size": 11},
        "hovertemplate": "<b>%{y}</b><br>Interest: %{x}/100<extra></extra>",
        "cliponaxis": False,
    }]

    chart_height = max(340, len(names) * 28 + 120)

    layout = _dark_layout(title, {
        "xaxis": {
            "title": "Relative Interest (0-100)",
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
        },
        "yaxis": {
            "automargin": True,
            "tickfont": {"size": 11},
        },
        "showlegend": False,
        "height": chart_height,
        "margin": {"l": 20, "r": 60, "t": 50, "b": 70},
        "annotations": [{
            "text": ("ℹ️ Based on English-language searches only. "
                     "Countries searching in other languages may not appear."),
            "xref": "paper", "yref": "paper",
            "x": 0.5, "y": -0.08,
            "showarrow": False,
            "font": {"size": 10, "color": "#7070a0"},
            "xanchor": "center",
        }],
    })

    fig = {"data": traces, "layout": layout, "config": _plotly_config()}
    return _fig_to_html(fig, "trends_region_chart")


# ── Dashboard HTML completa ──────────────────────────────────────────── #

def generate_dashboard_html(
    articles: list,
    query_topic: str = "",
    evidence_score: Optional[int] = None,
    article_counts: Optional[dict] = None,
    trends_data: Optional[dict] = None,
) -> str:
    """
    Generate the complete Charts tab HTML with Plotly charts.
    Loaded into QWebEngineView after each search.

    Phase 3 charts: Publication Trend, Evidence Pyramid, Top Journals.
    Phase 4 addition: Google Trends charts (if trends_data is provided).
    """
    if not articles:
        return _full_html_wrapper(
            "<div class='no-data'>No articles available.<br>"
            "Please run a PubMed search first.</div>",
            query_topic
        )

    # Always compute article_counts directly from articles in memory
    # so the stats panel is always accurate regardless of DB state
    computed_counts = _compute_article_counts(articles)
    if article_counts:
        # Merge: prefer passed values if non-zero, else use computed
        for k, v in computed_counts.items():
            if not article_counts.get(k):
                article_counts[k] = v
    else:
        article_counts = computed_counts

    html_trend = publication_trend(articles, "Publication Trend")
    html_pyramid = evidence_pyramid(articles, "Evidence Pyramid")
    html_journals = journal_distribution(articles, top_n=10, title="Top 10 Journals")

    stats_html = _build_stats_panel(
        n_articles=len(articles),
        evidence_score=evidence_score,
        article_counts=article_counts
    )

    # ── Phase 4: Google Trends section ──
    trends_section = ""
    if trends_data and trends_data.get('interest_over_time'):
        html_trends_timeline = trends_interest_timeline(
            trends_data, articles=articles
        )
        html_trends_queries = trends_related_queries(trends_data)
        html_trends_region = trends_region_chart(trends_data, top_n=20)

        # Trends stats mini-panel
        t_direction = trends_data.get('trend_direction', 'stable')
        t_icon = "📈" if t_direction == "rising" else ("📉" if t_direction == "declining" else "➡️")
        t_peak = trends_data.get('peak_value', '—')
        t_current = trends_data.get('current_value', '—')
        t_points = trends_data.get('data_points_count', 0)

        trends_section = f"""
        <div class="section-divider">
            <h2>🌐 Social & Web Perception — Google Trends</h2>
            <p class="subtitle">{t_points} data points analyzed</p>
        </div>

        <div class="stats-panel">
            <div class="stat-card">
                <div class="stat-number" style="font-size: 22px;">{t_icon} {t_direction.title()}</div>
                <div class="stat-label">Trend Direction</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{t_peak}</div>
                <div class="stat-label">Peak Interest</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{t_current}</div>
                <div class="stat-label">Current Interest</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{t_points}</div>
                <div class="stat-label">Data Points</div>
            </div>
        </div>

        <div class="chart-grid">
            <div class="chart-card">
                <h3>📈 Search Interest Over Time</h3>
                {html_trends_timeline}
            </div>
            <div class="chart-card">
                <h3>🔍 Top Related Queries</h3>
                {html_trends_queries}
            </div>
            <div class="chart-card">
                <h3>🌍 Interest by Region</h3>
                {html_trends_region}
            </div>
        </div>
        """

    elif trends_data is not None and not trends_data.get('interest_over_time'):
        # Trends were fetched but Google returned no data
        topic_str = trends_data.get('topic', 'this topic')
        trends_section = f"""
        <div class="section-divider">
            <h2>🌐 Social & Web Perception — Google Trends</h2>
        </div>
        <div class="trends-no-data">
            <span class="trends-no-data-icon">🔍</span>
            <p class="trends-no-data-title">No Google Trends data available</p>
            <p class="trends-no-data-text">
                Google Trends returned no results for "<b>{topic_str}</b>".<br>
                This typically happens with highly specialized medical terms that are
                rarely searched by the general public.<br>
                The topic may be well-established in scientific literature but has
                insufficient web search volume for Google to report trends data.
            </p>
        </div>
        """

    content = f"""
    <div class="header-section">
        <h2>📊 Dashboard — {query_topic or 'Analysis'}</h2>
        <p class="subtitle">{len(articles)} articles analyzed</p>
    </div>

    {stats_html}

    <div class="chart-grid">
        <div class="chart-card">
            <h3>📅 Publication Trend by Year</h3>
            {html_trend}
        </div>
        <div class="chart-card">
            <h3>🔺 Evidence Pyramid</h3>
            {html_pyramid}
        </div>
        <div class="chart-card">
            <h3>📰 Top 10 Journals</h3>
            {html_journals}
        </div>
    </div>

    {trends_section}

    """

    return _full_html_wrapper(content, query_topic)


def _compute_article_counts(articles: list) -> dict:
    """Compute RCT, meta-analysis, review and guideline counts from articles list."""
    rct = sum(
        1 for a in articles
        if any(t in ["Randomized Controlled Trial", "Clinical Trial"]
               for t in (a.get("article_types", []) if isinstance(a, dict) else []))
    )
    meta = sum(
        1 for a in articles
        if any(t in ["Meta-Analysis", "Systematic Review"]
               for t in (a.get("article_types", []) if isinstance(a, dict) else []))
    )
    reviews = sum(
        1 for a in articles
        if any(t == "Review"
               for t in (a.get("article_types", []) if isinstance(a, dict) else []))
    )
    guidelines = sum(
        1 for a in articles
        if any(t == "Practice Guideline"
               for t in (a.get("article_types", []) if isinstance(a, dict) else []))
    )
    return {"rct": rct, "meta": meta, "reviews": reviews, "guidelines": guidelines}


def _build_stats_panel(
    n_articles: int,
    evidence_score: Optional[int],
    article_counts: dict
) -> str:
    """Build the summary statistics panel above the charts."""
    rct = article_counts.get("rct", "—")
    meta = article_counts.get("meta", "—")
    reviews = article_counts.get("reviews", "—")
    guidelines = article_counts.get("guidelines", "—")
    score_str = f"{evidence_score}/100" if evidence_score is not None else "—"
    score_color = (
        "#70c070" if (evidence_score or 0) >= 70 else
        "#feca57" if (evidence_score or 0) >= 40 else
        "#ff6b6b" if evidence_score is not None else
        "#a0a0c0"
    )

    return f"""
    <div class="stats-panel">
        <div class="stat-card">
            <div class="stat-number">{n_articles}</div>
            <div class="stat-label">Total Articles</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{rct}</div>
            <div class="stat-label">RCTs / Clinical Trials</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{meta}</div>
            <div class="stat-label">Meta-Analyses / SR</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{reviews}</div>
            <div class="stat-label">Reviews</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{guidelines}</div>
            <div class="stat-label">Guidelines</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: {score_color}">{score_str}</div>
            <div class="stat-label">Evidence Score</div>
        </div>
    </div>
    """


def _fig_to_html(fig: dict, div_id: str) -> str:
    """Convert a Plotly figure dict into an HTML div with inline script."""
    fig_json = json.dumps(fig, ensure_ascii=False)
    return f"""
    <div id="{div_id}" class="plotly-chart"></div>
    <script>
        (function() {{
            var figData = {fig_json};
            Plotly.newPlot(
                '{div_id}',
                figData.data,
                figData.layout,
                figData.config
            );
        }})();
    </script>
    """


def _empty_chart_html(message: str) -> str:
    """Placeholder shown when no data is available for a chart."""
    return f"""
    <div class="empty-chart">
        <span class="empty-icon">📭</span>
        <p>{message}</p>
    </div>
    """


def _full_html_wrapper(content: str, title: str = "") -> str:
    """Wrap content in the full HTML page structure with styles and Plotly CDN."""
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIRS Dashboard — {title}</title>
    <script src="{PLOTLY_CDN}"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: {DARK_BG};
            color: {TEXT_COLOR};
            font-family: Arial, sans-serif;
            font-size: 13px;
            padding: 16px;
            overflow-y: auto;
        }}
        .header-section {{
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid #2a2a5a;
        }}
        .header-section h2 {{
            font-size: 18px;
            color: #c0c0e0;
            margin-bottom: 4px;
        }}
        .subtitle {{
            color: #7070a0;
            font-size: 12px;
        }}
        .stats-panel {{
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: #22223a;
            border: 1px solid #2a2a5a;
            border-radius: 8px;
            padding: 12px 20px;
            text-align: center;
            min-width: 100px;
            flex: 1;
        }}
        .stat-number {{
            font-size: 26px;
            font-weight: bold;
            color: #a0c0ff;
            line-height: 1.2;
        }}
        .stat-label {{
            font-size: 11px;
            color: #7070a0;
            margin-top: 4px;
        }}
        .chart-grid {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .chart-row {{
            display: flex;
            gap: 16px;
        }}
        .chart-card {{
            background: #22223a;
            border: 1px solid #2a2a5a;
            border-radius: 8px;
            padding: 16px;
        }}
        .chart-card h3 {{
            font-size: 13px;
            color: #a0a0c0;
            margin-bottom: 12px;
            font-weight: 600;
        }}
        .full-width {{ width: 100%; }}
        .half-width {{ flex: 1; min-width: 0; }}
        .plotly-chart {{
            width: 100%;
            min-height: 280px;
        }}
        .empty-chart {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 200px;
            color: #5050a0;
        }}
        .empty-icon {{ font-size: 36px; margin-bottom: 8px; }}
        .section-divider {{
            margin-top: 32px;
            padding-top: 20px;
            padding-bottom: 12px;
            border-top: 2px solid #3a3a6a;
            margin-bottom: 16px;
        }}
        .section-divider h2 {{
            font-size: 18px;
            color: #c0c0e0;
            margin-bottom: 4px;
        }}
        .trends-no-data {{
            background: #22223a;
            border: 1px solid #2a2a5a;
            border-radius: 8px;
            padding: 40px 30px;
            text-align: center;
            margin-top: 16px;
        }}
        .trends-no-data-icon {{
            font-size: 40px;
            display: block;
            margin-bottom: 12px;
        }}
        .trends-no-data-title {{
            font-size: 16px;
            font-weight: bold;
            color: #a0a0c0;
            margin-bottom: 12px;
        }}
        .trends-no-data-text {{
            font-size: 13px;
            color: #7070a0;
            line-height: 1.7;
            max-width: 600px;
            margin: 0 auto;
        }}
        .no-data {{
            text-align: center;
            color: #5050a0;
            padding: 80px 20px;
            font-size: 16px;
            line-height: 2;
        }}
        ::-webkit-scrollbar {{ width: 8px; background: {DARK_BG}; }}
        ::-webkit-scrollbar-thumb {{
            background: #3a3a6a; border-radius: 4px;
        }}
    </style>
</head>
<body>
    {content}
</body>
</html>"""


# ── Test standalone ─────────────────────────────────────────────────── #

if __name__ == "__main__":
    import os

    test_articles = [
        {"article_types": ["Randomized Controlled Trial"], "pub_date": "2023", "journal": "NEJM"},
        {"article_types": ["Randomized Controlled Trial"], "pub_date": "2022", "journal": "Lancet"},
        {"article_types": ["Meta-Analysis"], "pub_date": "2023", "journal": "JAMA"},
        {"article_types": ["Systematic Review"], "pub_date": "2022", "journal": "BMJ"},
        {"article_types": ["Practice Guideline"], "pub_date": "2021", "journal": "EJCTS"},
        {"article_types": ["Journal Article"], "pub_date": "2022", "journal": "NEJM"},
        {"article_types": ["Journal Article"], "pub_date": "2021", "journal": "Circulation"},
        {"article_types": ["Journal Article"], "pub_date": "2020", "journal": "EJCTS"},
        {"article_types": ["Clinical Trial"], "pub_date": "2023", "journal": "Lancet"},
        {"article_types": ["Review"], "pub_date": "2022", "journal": "NEJM"},
    ]

    html = generate_dashboard_html(
        articles=test_articles,
        query_topic="Test Query",
        evidence_score=72,
        article_counts={"rct": 2, "meta": 1, "guidelines": 1}
    )

    with open("test_charts_output.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML generato: {os.path.abspath('test_charts_output.html')}")
