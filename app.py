"""
MIRS — Medical Intelligence Report System (Streamlit Web Version)
app.py

A web-based medical intelligence tool that combines PubMed literature
analysis, Google Trends data, Evidence Strength Scoring, and AI-powered
synthesis to generate comprehensive medical intelligence reports.

Author: Michele D. Pierri
Version: 1.0-web (March 2026)
"""

import streamlit as st
import time
import json
import io
import tempfile
import os
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Page config (MUST be first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MIRS — Medical Intelligence Report System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
import config

# ---------------------------------------------------------------------------
# Usage limits
# ---------------------------------------------------------------------------

DAILY_GLOBAL_CAP = 20        # Max analyses per day (all users combined)
SESSION_CAP = 5              # Max analyses per session (single user)
MAX_ARTICLES_PER_SEARCH = 1000  # Max articles fetched per query

# Path to persist daily counter (survives across sessions)
_USAGE_FILE = os.path.join(tempfile.gettempdir(), "mirs_daily_usage.json")


def _get_daily_usage() -> dict:
    """Read daily usage counter from disk."""
    try:
        if os.path.exists(_USAGE_FILE):
            with open(_USAGE_FILE, "r") as f:
                data = json.load(f)
            # Reset if it's a new day
            if data.get("date") != str(date.today()):
                return {"date": str(date.today()), "count": 0}
            return data
    except Exception:
        pass
    return {"date": str(date.today()), "count": 0}


def _increment_daily_usage():
    """Increment and persist the daily usage counter."""
    data = _get_daily_usage()
    data["count"] += 1
    data["date"] = str(date.today())
    try:
        with open(_USAGE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _check_usage_limits() -> str | None:
    """
    Check all usage limits before running a search.

    Returns:
        None if OK, or an error message string if a limit is reached.
    """
    # Check session cap
    session_count = st.session_state.get("session_search_count", 0)
    if session_count >= SESSION_CAP:
        return (
            f"⚠️ Session limit reached ({SESSION_CAP} analyses per session). "
            "Please reload the page to start a new session, or contact "
            "Michele Danilo Pierri for assistance."
        )

    # Check daily global cap
    daily = _get_daily_usage()
    if daily["count"] >= DAILY_GLOBAL_CAP:
        return (
            f"⚠️ Daily limit reached ({DAILY_GLOBAL_CAP} analyses per day). "
            "The system will reset automatically tomorrow. "
            "For urgent needs, contact Michele Danilo Pierri."
        )

    return None

# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

def _check_auth():
    """Simple password gate for beta testers."""
    if not config.APP_PASSWORD:
        return True  # No password configured — open access

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        """
        <style>
        .auth-container {
            max-width: 420px;
            margin: 12vh auto 0 auto;
            padding: 2.5rem 2rem;
            border: 1px solid #334;
            border-radius: 12px;
            background: linear-gradient(145deg, #0e1117 0%, #161b22 100%);
        }
        .auth-title {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin-bottom: 0.25rem;
        }
        .auth-subtitle {
            text-align: center;
            color: #8b949e;
            font-size: 0.85rem;
            margin-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="auth-title">🧬 MIRS</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="auth-subtitle">Medical Intelligence Report System<br>'
            '<span style="color:#58a6ff;">Beta Access</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="text-align:center; margin-bottom:1.5rem;">'
            '<span style="font-size:1.05rem; color:#c9d1d9; font-weight:500;">'
            'Michele Danilo Pierri MD, PhD</span><br>'
            '<a href="https://micheledpierri.com" target="_blank" '
            'style="color:#58a6ff; text-decoration:none; font-size:0.95rem;">'
            'micheledpierri.com</a>'
            '</div>',
            unsafe_allow_html=True,
        )

        pwd = st.text_input("Password", type="password", key="auth_pwd",
                            placeholder="Enter beta access password")
        if st.button("Enter", use_container_width=True, type="primary"):
            if pwd == config.APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

def _inject_css():
    st.markdown(
        """
        <style>
        /* Stat cards */
        .stat-card {
            background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #58a6ff;
            line-height: 1.2;
        }
        .stat-label {
            font-size: 0.75rem;
            color: #8b949e;
            margin-top: 0.3rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .score-green { color: #3fb950 !important; }
        .score-yellow { color: #d29922 !important; }
        .score-red { color: #f85149 !important; }

        /* Section headers */
        .section-header {
            font-size: 1.15rem;
            font-weight: 600;
            color: #c9d1d9;
            border-bottom: 1px solid #21262d;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
        }

        /* Article table tweaks */
        .stDataFrame { font-size: 0.85rem; }

        /* Footer */
        .mirs-footer {
            text-align: center;
            color: #484f58;
            font-size: 0.72rem;
            margin-top: 3rem;
            padding: 1rem 0;
            border-top: 1px solid #21262d;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    """Initialize session state with defaults."""
    defaults = {
        "articles": [],
        "evidence_result": None,
        "trends_data": None,
        "synthesis_text": "",
        "query_topic": "",
        "search_done": False,
        "synthesis_done": False,
        "session_search_count": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _score_css_class(score):
    if score is None:
        return ""
    if score >= 70:
        return "score-green"
    if score >= 40:
        return "score-yellow"
    return "score-red"


# ---------------------------------------------------------------------------
# Sidebar — Search Configuration
# ---------------------------------------------------------------------------

def _render_sidebar():
    """Render the sidebar with search configuration."""
    with st.sidebar:
        st.markdown("## 🧬 MIRS")
        st.caption("Medical Intelligence Report System")
        st.caption("Michele Danilo Pierri MD, PhD")
        st.divider()

        st.markdown("### New Analysis")

        topic = st.text_input(
            "Clinical Topic",
            placeholder='e.g. "aortic dissection type A repair"',
            help="Enter a clinical topic. Use specific terms for better results.",
        )

        col1, col2 = st.columns(2)
        with col1:
            date_from = st.text_input("From (YYYY/MM/DD)", value="", placeholder="2019/01/01")
        with col2:
            date_to = st.text_input("To (YYYY/MM/DD)", value="", placeholder="2025/12/31")

        article_type_options = [
            "Clinical Trial",
            "Meta-Analysis",
            "Randomized Controlled Trial",
            "Review",
            "Systematic Review",
            "Practice Guideline",
            "Comparative Study",
            "Case Reports",
        ]
        selected_types = st.multiselect(
            "Article Types (optional)",
            article_type_options,
            help="Leave empty to search all types.",
        )

        fetch_trends = st.checkbox("Fetch Google Trends data", value=True)

        st.divider()

        run_search = st.button(
            "🔍  Run Analysis",
            use_container_width=True,
            type="primary",
            disabled=(not topic.strip()),
        )

        # Show previous query info
        if st.session_state.get("search_done"):
            st.divider()
            st.markdown("### Current Analysis")
            st.markdown(f"**{st.session_state['query_topic']}**")
            n = len(st.session_state["articles"])
            st.caption(f"{n} articles loaded")

        # Show usage info
        daily = _get_daily_usage()
        session_count = st.session_state.get("session_search_count", 0)
        remaining_s = SESSION_CAP - session_count
        remaining_d = DAILY_GLOBAL_CAP - daily["count"]
        st.divider()
        st.caption(f"🔢 Session: {remaining_s}/{SESSION_CAP} analyses left")
        st.caption(f"📅 Daily: {remaining_d}/{DAILY_GLOBAL_CAP} analyses left")

        st.divider()
        st.markdown(
            '<div class="mirs-footer">'
            'MIRS v1.0-web<br>'
            'Michele Danilo Pierri MD, PhD<br>'
            '<a href="https://micheledpierri.com" target="_blank" '
            'style="color:#58a6ff; text-decoration:none;">micheledpierri.com</a><br>'
            '<span style="margin-top:4px; display:inline-block;">'
            'Data: PubMed · Google Trends · Claude AI</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    return {
        "run": run_search,
        "topic": topic.strip(),
        "date_from": date_from.strip() or None,
        "date_to": date_to.strip() or None,
        "article_types": selected_types or None,
        "fetch_trends": fetch_trends,
    }


# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------

def _run_search(params: dict):
    """Execute PubMed search + optional Google Trends fetch."""
    # --- Usage limit check ---
    limit_msg = _check_usage_limits()
    if limit_msg:
        st.error(limit_msg)
        return

    from agents.pubmed_agents import PubMedAgent
    from analysis.evidence_scorer import calculate_evidence_score

    topic = params["topic"]
    st.session_state["query_topic"] = topic
    st.session_state["synthesis_text"] = ""
    st.session_state["synthesis_done"] = False

    progress = st.status(f"Analyzing: **{topic}**", expanded=True)

    with progress:
        # --- Step 1: PubMed Count ---
        st.write("🔍 Counting PubMed results...")
        agent = PubMedAgent()
        count = agent.count(
            query=topic,
            date_from=params["date_from"],
            date_to=params["date_to"],
            article_types=params["article_types"],
        )

        if count > MAX_ARTICLES_PER_SEARCH:
            st.warning(
                f"⚠️ {count:,} articles match this query — "
                f"fetching the first {MAX_ARTICLES_PER_SEARCH:,}. "
                "Consider narrowing your search criteria for complete coverage."
            )

        if count == 0:
            st.error("No articles found. Try broadening your search.")
            return

        st.write(f"📊 Found **{count:,}** matching articles on PubMed")

        # --- Step 2: Fetch articles (capped) ---
        fetch_count = min(count, MAX_ARTICLES_PER_SEARCH)
        st.write(f"📥 Fetching metadata for {fetch_count:,} articles...")
        articles = agent.search_and_fetch(
            query=topic,
            max_results=MAX_ARTICLES_PER_SEARCH,
            date_from=params["date_from"],
            date_to=params["date_to"],
            article_types=params["article_types"],
        )

        if not articles:
            st.error("Failed to fetch articles. Please try again.")
            return

        # Convert to dicts for uniform handling
        article_dicts = []
        for art in articles:
            if isinstance(art, dict):
                article_dicts.append(art)
            else:
                article_dicts.append(art.to_dict() if hasattr(art, "to_dict") else art)

        st.session_state["articles"] = article_dicts
        st.write(f"✅ **{len(article_dicts)}** articles retrieved")

        # --- Step 3: Evidence Score ---
        st.write("📈 Calculating Evidence Strength Score...")
        ev_result = calculate_evidence_score(article_dicts)
        st.session_state["evidence_result"] = ev_result
        st.write(f"✅ Evidence Score: **{ev_result.total_score}/100**")

        # --- Step 4: Google Trends (optional) ---
        if params["fetch_trends"]:
            st.write("🌐 Fetching Google Trends data...")
            try:
                from agents.trends_agent import TrendsAgent
                trends_agent = TrendsAgent()
                trends_data = trends_agent.fetch_all(topic=topic)
                st.session_state["trends_data"] = trends_data
                n_points = trends_data.get("data_points_count", 0)
                if n_points > 0:
                    direction = trends_data.get("trend_direction", "stable")
                    st.write(f"✅ Google Trends: **{n_points}** data points — trend: **{direction}**")
                else:
                    st.write("ℹ️ Google Trends returned no data for this topic")
            except Exception as e:
                st.warning(f"Google Trends fetch failed: {e}")
                st.session_state["trends_data"] = None
        else:
            st.session_state["trends_data"] = None

        st.write("🎉 **Analysis complete!**")

    # Increment usage counters
    st.session_state["session_search_count"] = st.session_state.get("session_search_count", 0) + 1
    _increment_daily_usage()

    daily = _get_daily_usage()
    remaining_session = SESSION_CAP - st.session_state["session_search_count"]
    remaining_daily = DAILY_GLOBAL_CAP - daily["count"]
    st.caption(f"Usage: {remaining_session} analyses left this session · "
               f"{remaining_daily} left today")

    st.session_state["search_done"] = True


# ---------------------------------------------------------------------------
# Main content — Dashboard tabs
# ---------------------------------------------------------------------------

def _render_stat_cards():
    """Render the summary stat cards row."""
    articles = st.session_state["articles"]
    ev = st.session_state["evidence_result"]
    n = len(articles)

    # Count article types
    from report.charts import _compute_article_counts
    counts = _compute_article_counts(articles)

    score = ev.total_score if ev else None
    score_class = _score_css_class(score)
    score_str = f"{score}/100" if score is not None else "—"

    cols = st.columns(6)
    card_data = [
        ("Total Articles", str(n), ""),
        ("RCTs / CT", str(counts.get("rct", 0)), ""),
        ("Meta / SR", str(counts.get("meta", 0)), ""),
        ("Reviews", str(counts.get("reviews", 0)), ""),
        ("Guidelines", str(counts.get("guidelines", 0)), ""),
        ("Evidence Score", score_str, score_class),
    ]
    for col, (label, value, css) in zip(cols, card_data):
        with col:
            st.markdown(
                f'<div class="stat-card">'
                f'<div class="stat-value {css}">{value}</div>'
                f'<div class="stat-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_overview_tab():
    """Render the Overview tab with charts."""
    import plotly.graph_objects as go
    from report.charts import (
        _extract_year, _classify_article_type, _get_field,
        STUDY_COLORS, EVIDENCE_HIERARCHY, DARK_BG, DARK_PAPER,
        TEXT_COLOR, GRID_COLOR, AXIS_COLOR,
    )
    from collections import Counter, defaultdict

    articles = st.session_state["articles"]

    # --- Publication Trend ---
    st.markdown('<div class="section-header">📅 Publication Trend by Year</div>',
                unsafe_allow_html=True)

    year_type_count = defaultdict(Counter)
    for art in articles:
        year = _extract_year(_get_field(art, "pub_date"))
        art_type = _classify_article_type(_get_field(art, "article_types"))
        if year is not None:
            year_type_count[year][art_type] += 1

    if year_type_count:
        years = sorted(year_type_count.keys())
        all_types = set()
        for c in year_type_count.values():
            all_types.update(c.keys())
        type_order = [t for t in EVIDENCE_HIERARCHY if t in all_types]

        fig = go.Figure()
        for stype in type_order:
            y_vals = [year_type_count[yr].get(stype, 0) for yr in years]
            if sum(y_vals) == 0:
                continue
            fig.add_trace(go.Bar(
                name=stype, x=years, y=y_vals,
                marker_color=STUDY_COLORS.get(stype, "#888"),
                hovertemplate=f"<b>{stype}</b><br>Year: %{{x}}<br>Articles: %{{y}}<extra></extra>"
            ))

        fig.update_layout(
            barmode="stack", template="plotly_dark",
            paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
            font=dict(color=TEXT_COLOR),
            xaxis=dict(title="Year", gridcolor=GRID_COLOR),
            yaxis=dict(title="Articles", gridcolor=GRID_COLOR),
            height=400, margin=dict(l=50, r=20, t=30, b=50),
            legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No publication year data available.")

    # --- Evidence Pyramid + Top Journals side by side ---
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">🔺 Evidence Pyramid</div>',
                    unsafe_allow_html=True)
        type_counts = Counter()
        for art in articles:
            art_type = _classify_article_type(_get_field(art, "article_types"))
            type_counts[art_type] += 1

        if type_counts:
            sorted_types = sorted(type_counts.keys(),
                                  key=lambda t: EVIDENCE_HIERARCHY.get(t, 99))
            fig2 = go.Figure(go.Pie(
                labels=[f"{t} ({type_counts[t]})" for t in sorted_types],
                values=[type_counts[t] for t in sorted_types],
                marker=dict(colors=[STUDY_COLORS.get(t, "#888") for t in sorted_types]),
                hole=0.38, textinfo="percent", textposition="inside",
            ))
            fig2.update_layout(
                template="plotly_dark",
                paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
                font=dict(color=TEXT_COLOR),
                height=380, margin=dict(l=20, r=20, t=20, b=80),
                legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
            )
            st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.markdown('<div class="section-header">📰 Top 10 Journals</div>',
                    unsafe_allow_html=True)
        journal_counts = Counter()
        for art in articles:
            j = _get_field(art, "journal")
            if j and j.strip():
                journal_counts[j.strip()] += 1

        if journal_counts:
            top10 = journal_counts.most_common(10)
            journals = [j for j, _ in reversed(top10)]
            counts = [c for _, c in reversed(top10)]
            fig3 = go.Figure(go.Bar(
                x=counts, y=journals, orientation="h",
                marker=dict(color="#4a6ea8"),
                text=[str(c) for c in counts], textposition="auto",
            ))
            fig3.update_layout(
                template="plotly_dark",
                paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
                font=dict(color=TEXT_COLOR),
                xaxis=dict(title="Articles", gridcolor=GRID_COLOR),
                yaxis=dict(automargin=True),
                height=380, margin=dict(l=20, r=50, t=20, b=50),
            )
            st.plotly_chart(fig3, use_container_width=True)


def _render_trends_tab():
    """Render the Google Trends tab."""
    import plotly.graph_objects as go
    from report.charts import DARK_BG, DARK_PAPER, TEXT_COLOR, GRID_COLOR

    trends = st.session_state.get("trends_data")

    if not trends or not trends.get("interest_over_time"):
        st.info(
            "No Google Trends data available for this topic. "
            "This typically happens with highly specialized medical terms "
            "that have low public search volume."
        )
        return

    iot = trends["interest_over_time"]
    dates = [dp["date"] for dp in iot]
    values = [dp["value"] for dp in iot]

    # Trend stats
    direction = trends.get("trend_direction", "stable")
    d_icon = "📈" if direction == "rising" else ("📉" if direction == "declining" else "➡️")

    cols = st.columns(4)
    trend_stats = [
        (f"{d_icon} {direction.title()}", "Trend Direction"),
        (str(trends.get("peak_value", "—")), "Peak Interest"),
        (str(trends.get("current_value", "—")), "Current Interest"),
        (str(trends.get("data_points_count", 0)), "Data Points"),
    ]
    for col, (val, lbl) in zip(cols, trend_stats):
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="stat-value" style="font-size:1.3rem">{val}</div>'
                f'<div class="stat-label">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("")  # spacer

    # --- Interest Over Time ---
    st.markdown('<div class="section-header">📈 Search Interest Over Time</div>',
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values, mode="lines",
        line=dict(color="#54a0ff", width=2),
        fill="tozeroy", fillcolor="rgba(84,160,255,0.12)",
        hovertemplate="<b>%{x}</b><br>Interest: %{y}/100<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(gridcolor=GRID_COLOR, type="date"),
        yaxis=dict(title="Search Interest (0-100)", gridcolor=GRID_COLOR, range=[0, 105]),
        height=380, margin=dict(l=50, r=20, t=20, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Related Queries + Region side by side ---
    col1, col2 = st.columns(2)

    with col1:
        top_q = trends.get("related_queries_top", [])[:15]
        if top_q:
            st.markdown('<div class="section-header">🔍 Top Related Queries</div>',
                        unsafe_allow_html=True)
            queries = [q["query"] for q in reversed(top_q)]
            vals = [q["value"] for q in reversed(top_q)]
            fig_q = go.Figure(go.Bar(
                x=vals, y=queries, orientation="h",
                marker=dict(color="#54a0ff"), text=[str(v) for v in vals],
                textposition="auto",
            ))
            fig_q.update_layout(
                template="plotly_dark",
                paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
                font=dict(color=TEXT_COLOR),
                xaxis=dict(title="Relevance (0-100)", gridcolor=GRID_COLOR),
                yaxis=dict(automargin=True),
                height=max(300, len(queries) * 28 + 80),
                margin=dict(l=20, r=50, t=20, b=50),
            )
            st.plotly_chart(fig_q, use_container_width=True)

    with col2:
        regions = trends.get("interest_by_region", [])[:20]
        if regions:
            st.markdown('<div class="section-header">🌍 Interest by Region</div>',
                        unsafe_allow_html=True)
            names = [r["region"] for r in reversed(regions)]
            vals_r = [r["value"] for r in reversed(regions)]
            fig_r = go.Figure(go.Bar(
                x=vals_r, y=names, orientation="h",
                marker=dict(color="#00d2d3"), text=[str(v) for v in vals_r],
                textposition="auto",
            ))
            fig_r.update_layout(
                template="plotly_dark",
                paper_bgcolor=DARK_PAPER, plot_bgcolor=DARK_BG,
                font=dict(color=TEXT_COLOR),
                xaxis=dict(title="Interest (0-100)", gridcolor=GRID_COLOR),
                yaxis=dict(automargin=True),
                height=max(300, len(names) * 26 + 80),
                margin=dict(l=20, r=50, t=20, b=50),
            )
            st.plotly_chart(fig_r, use_container_width=True)


def _render_articles_tab():
    """Render the articles data table with editable include/exclude and click-to-view abstract."""
    import pandas as pd

    articles = st.session_state["articles"]
    if not articles:
        st.info("No articles loaded.")
        return

    rows = []
    for art in articles:
        authors = art.get("authors", [])
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except Exception:
                authors = [authors]
        first_author = authors[0] if authors else "—"
        if len(authors) > 1:
            first_author += " et al."

        types = art.get("article_types", [])
        if isinstance(types, str):
            try:
                types = json.loads(types)
            except Exception:
                types = [types]

        rows.append({
            "Included": bool(art.get("included", True)),
            "PMID": art.get("pmid", ""),
            "Year": str(art.get("pub_date", ""))[:4],
            "Title": art.get("title", ""),
            "First Author": first_author,
            "Journal": art.get("journal", ""),
            "Type": ", ".join(types[:2]) if types else "—",
        })

    df = pd.DataFrame(rows)

    # Filters
    col1, col2 = st.columns([1, 3])
    with col1:
        type_filter = st.selectbox("Filter by type", ["All"] + sorted(set(
            t for art in articles
            for t in (art.get("article_types", [])
                      if isinstance(art.get("article_types"), list)
                      else [])
        )))
    with col2:
        text_filter = st.text_input("Search titles...", placeholder="Type to filter")

    if type_filter != "All":
        mask = df["Type"].str.contains(type_filter, case=False, na=False)
        df = df[mask]

    if text_filter:
        mask = df["Title"].str.contains(text_filter, case=False, na=False)
        df = df[mask]

    n_included = sum(1 for a in articles if a.get("included", True))
    st.caption(f"Showing {len(df)} of {len(articles)} articles · "
               f"{n_included} included in analysis · "
               f"Toggle checkboxes to include/exclude · Click a row to view the abstract")

    # Editable dataframe with functional checkboxes + row selection
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=500,
        column_config={
            "Included": st.column_config.CheckboxColumn("✓", width=50, default=True),
            "PMID": st.column_config.TextColumn("PMID", width=90, disabled=True),
            "Year": st.column_config.TextColumn("Year", width=55, disabled=True),
            "Title": st.column_config.TextColumn("Title", width=320, disabled=True),
            "First Author": st.column_config.TextColumn("First Author", width=130, disabled=True),
            "Journal": st.column_config.TextColumn("Journal", width=150, disabled=True),
            "Type": st.column_config.TextColumn("Type", width=120, disabled=True),
        },
        disabled=False,
        num_rows="fixed",
        key="article_editor",
        on_change=None,
    )

    # Sync checkbox changes back to session state articles
    if edited_df is not None:
        for idx, row in edited_df.iterrows():
            pmid = row["PMID"]
            included = bool(row["Included"])
            for art in articles:
                if art.get("pmid") == pmid:
                    art["included"] = included
                    break

    # Recalculate evidence score if inclusion changed
    n_included_now = sum(1 for a in articles if a.get("included", True))
    if n_included_now != st.session_state.get("_last_n_included", n_included_now):
        from analysis.evidence_scorer import calculate_evidence_score
        included_arts = [a for a in articles if a.get("included", True)]
        ev_result = calculate_evidence_score(included_arts)
        st.session_state["evidence_result"] = ev_result
        st.session_state["_last_n_included"] = n_included_now
        st.toast(f"Evidence Score recalculated: {ev_result.total_score}/100 "
                 f"({n_included_now} articles included)")

    if "_last_n_included" not in st.session_state:
        st.session_state["_last_n_included"] = n_included_now

    # Article detail — use selectbox for quick article selection
    st.divider()
    st.markdown('<div class="section-header">📄 Article Detail</div>',
                unsafe_allow_html=True)

    # Build options list from currently visible articles
    pmid_options = ["— Select an article —"] + [
        f"{row['PMID']} · {row['Year']} · {row['Title'][:80]}"
        for _, row in edited_df.iterrows()
    ]

    selected_option = st.selectbox(
        "Select article",
        pmid_options,
        label_visibility="collapsed",
    )

    if selected_option != "— Select an article —":
        selected_pmid = selected_option.split(" · ")[0]
        match = [a for a in articles if a.get("pmid") == selected_pmid]
        if match:
            art = match[0]
            st.markdown(f"### {art.get('title', '')}")
            authors = art.get("authors", [])
            if isinstance(authors, str):
                try:
                    authors = json.loads(authors)
                except Exception:
                    authors = [authors]
            st.caption(f"{', '.join(authors[:5])}{'...' if len(authors) > 5 else ''}")
            st.caption(f"{art.get('journal', '')} · {art.get('pub_date', '')} · PMID: {selected_pmid}")
            if art.get("doi"):
                st.caption(f"DOI: [{art['doi']}](https://doi.org/{art['doi']})")
            abstract = art.get("abstract", "")
            if abstract:
                st.markdown(abstract)
            else:
                st.info("No abstract available for this article.")


def _render_synthesis_tab():
    """Render the AI Synthesis tab."""
    articles = st.session_state["articles"]
    if not articles:
        st.info("Run a search first to generate synthesis.")
        return

    # Check if synthesis already done
    if st.session_state.get("synthesis_done") and st.session_state.get("synthesis_text"):
        st.markdown(st.session_state["synthesis_text"])
    else:
        if not config.ANTHROPIC_API_KEY:
            st.error(
                "Anthropic API key not configured. "
                "AI synthesis is not available."
            )
            return

        st.info(
            "Click the button below to generate an AI-powered synthesis "
            "of the literature and gap analysis. This calls the Claude API "
            "and may take 30-60 seconds."
        )

        if st.button("🤖  Generate AI Synthesis", type="primary", use_container_width=True):
            with st.spinner("Generating synthesis with Claude AI..."):
                try:
                    from llm.synthesizer import synthesize_report

                    ev = st.session_state.get("evidence_result")
                    result = synthesize_report(
                        topic=st.session_state["query_topic"],
                        articles=articles,
                        evidence_score=ev.total_score if ev else None,
                        trends_data=st.session_state.get("trends_data"),
                        api_key=config.ANTHROPIC_API_KEY,
                    )
                    st.session_state["synthesis_text"] = result
                    st.session_state["synthesis_done"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Synthesis failed: {e}")


def _render_export_tab():
    """Render the Export tab with PDF and CSV downloads."""
    articles = st.session_state["articles"]
    if not articles:
        st.info("Run a search first to export results.")
        return

    st.markdown('<div class="section-header">📤 Export Results</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📄 PDF Report")
        st.caption("Professional print-ready report with cover page, "
                   "summary statistics, article table, and AI synthesis.")
        include_abstracts = st.checkbox("Include abstracts in PDF", value=False)

        if st.button("Generate PDF", use_container_width=True):
            with st.spinner("Generating PDF..."):
                try:
                    from report.pdf_generator import generate_pdf_report

                    ev = st.session_state.get("evidence_result")
                    tmp_path = os.path.join(tempfile.gettempdir(), f"mirs_report_{id(articles)}.pdf")
                    generate_pdf_report(
                        output_path=tmp_path,
                        articles=articles,
                        topic=st.session_state["query_topic"],
                        evidence_score=ev.total_score if ev else None,
                        synthesis_text=st.session_state.get("synthesis_text", ""),
                        include_abstracts=include_abstracts,
                    )
                    with open(tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                    topic_slug = st.session_state["query_topic"][:40].replace(" ", "_")
                    st.download_button(
                        "⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"MIRS_{topic_slug}_{datetime.now():%Y%m%d}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")

    with col2:
        st.markdown("#### 📊 CSV Data")
        st.caption("Article database in CSV format, "
                   "compatible with Excel and Google Sheets.")
        include_csv_abstracts = st.checkbox("Include abstracts in CSV", value=True)

        if st.button("Generate CSV", use_container_width=True):
            with st.spinner("Generating CSV..."):
                try:
                    from report.csv_exporter import export_articles_csv

                    tmp_path = os.path.join(tempfile.gettempdir(), f"mirs_articles_{id(articles)}.csv")
                    export_articles_csv(
                        output_path=tmp_path,
                        articles=articles,
                        include_abstracts=include_csv_abstracts,
                    )
                    with open(tmp_path, "r", encoding="utf-8-sig") as f:
                        csv_data = f.read()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                    topic_slug = st.session_state["query_topic"][:40].replace(" ", "_")
                    st.download_button(
                        "⬇️ Download CSV",
                        data=csv_data,
                        file_name=f"MIRS_{topic_slug}_{datetime.now():%Y%m%d}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"CSV generation failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _init_state()
    _inject_css()

    if not _check_auth():
        st.stop()

    params = _render_sidebar()

    # Run search if requested
    if params["run"]:
        _run_search(params)
        st.rerun()

    # If no search done yet, show welcome screen
    if not st.session_state.get("search_done"):
        st.markdown(
            """
            <div style="text-align:center; margin-top: 10vh;">
            <h1 style="font-size:2.5rem; font-weight:700; letter-spacing:0.06em;">
            🧬 MIRS
            </h1>
            <p style="color:#8b949e; font-size:1.1rem; margin-bottom:2rem;">
            Medical Intelligence Report System
            </p>
            <p style="color:#58a6ff; font-size:0.95rem; max-width:600px; margin:0 auto; line-height:1.7;">
            Enter a clinical topic in the sidebar to generate a comprehensive
            medical intelligence report combining PubMed literature analysis,
            Google Trends data, Evidence Strength Scoring, and AI-powered synthesis.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # --- Render dashboard ---
    topic = st.session_state["query_topic"]
    st.markdown(f"## 📊 {topic}")
    st.caption(f"{len(st.session_state['articles'])} articles · "
               f"Analyzed {datetime.now():%B %d, %Y}")

    _render_stat_cards()
    st.markdown("")

    tab_overview, tab_trends, tab_articles, tab_synthesis, tab_export = st.tabs([
        "📊 Overview",
        "🌐 Google Trends",
        "📋 Articles",
        "🤖 AI Synthesis",
        "📤 Export",
    ])

    with tab_overview:
        _render_overview_tab()

    with tab_trends:
        _render_trends_tab()

    with tab_articles:
        _render_articles_tab()

    with tab_synthesis:
        _render_synthesis_tab()

    with tab_export:
        _render_export_tab()


if __name__ == "__main__":
    main()
