# 🧬 MIRS — Medical Intelligence Report System

**A web-based medical intelligence tool that generates comprehensive evidence reports by combining PubMed literature analysis, Google Trends data, Evidence Strength Scoring, and AI-powered synthesis.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mirs-app.streamlit.app)

---

## Overview

MIRS bridges the gap between scientific evidence and public perception for any medical topic. Given a clinical query, it produces a structured intelligence report with quantitative metrics, interactive visualizations, and AI-generated narrative synthesis.

### Key Features

- **PubMed Literature Analysis** — searches and retrieves all matching articles with full metadata
- **Evidence Strength Score** — proprietary composite score (0–100) based on RCTs, meta-analyses, guidelines, concordance, and publication volume
- **Google Trends Integration** — tracks public search interest, related queries, and geographic patterns
- **AI Synthesis** — Claude-powered narrative combining Key Findings, Consensus & Controversies, and Gap Analysis
- **Evidence-Perception Gap Analysis** — identifies discrepancies between scientific evidence and public interest
- **Export** — PDF report (print-ready) and CSV data export

### Architecture

```
┌─────────────────────────────────────────┐
│            Streamlit Web UI             │
│  (Overview · Trends · Articles · AI · Export)  │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ PubMed │ │ Google │ │ Claude │
│ Agent  │ │ Trends │ │  API   │
│        │ │ Agent  │ │(Synth.)│
└────────┘ └────────┘ └────────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────┐
│  Evidence Scorer · Charts · PDF · CSV   │
└─────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- PubMed API key ([register here](https://www.ncbi.nlm.nih.gov/account/))
- Anthropic API key (for AI synthesis — [get one here](https://console.anthropic.com/))

### Local Installation

```bash
# Clone the repository
git clone https://github.com/micheledpierri/mirs-app.git
cd mirs-app

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your API keys

# Run
streamlit run app.py
```

### Secrets Configuration

Create `.streamlit/secrets.toml` (never commit this file):

```toml
PUBMED_API_KEY = "your_ncbi_api_key"
PUBMED_EMAIL = "your_email@example.com"
ANTHROPIC_API_KEY = "sk-ant-..."
APP_PASSWORD = "your_beta_password"
```

---

## Deployment on Streamlit Community Cloud

1. Push the repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo and select `app.py`
4. Add secrets in the Streamlit Cloud dashboard (Settings → Secrets):
   ```toml
   PUBMED_API_KEY = "..."
   PUBMED_EMAIL = "..."
   ANTHROPIC_API_KEY = "..."
   APP_PASSWORD = "..."
   ```
5. Deploy — the app will be live at `https://your-app.streamlit.app`

---

## Project Structure

```
mirs-app/
├── app.py                     # Main Streamlit application
├── config.py                  # Configuration (reads st.secrets)
├── requirements.txt           # Python dependencies
├── .streamlit/
│   ├── config.toml            # Streamlit theme (dark)
│   └── secrets.toml.example   # Secrets template
├── agents/
│   ├── pubmed_agents.py       # PubMed E-utilities search & fetch
│   └── trends_agent.py        # Google Trends via pytrends
├── analysis/
│   └── evidence_scorer.py     # Evidence Strength Score (0-100)
├── llm/
│   ├── prompts.py             # Prompt templates for Claude API
│   └── synthesizer.py         # Claude API integration
├── report/
│   ├── charts.py              # Plotly chart generators
│   ├── pdf_generator.py       # PDF report (fpdf2, light theme)
│   └── csv_exporter.py        # CSV article export
└── .gitignore
```

---

## Evidence Strength Score

The Evidence Strength Score is a composite metric (0–100) calculated as a weighted average:

| Component | Weight | What it measures |
|-----------|--------|------------------|
| RCT quality | 30% | Number of randomized controlled trials |
| Meta-analyses | 25% | Presence of concordant meta-analyses and systematic reviews |
| Guidelines | 20% | Recency of clinical practice guidelines (< 5 years) |
| Concordance | 15% | Diversity of evidence types (proxy for cross-source agreement) |
| Volume | 10% | Total publication volume |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web framework | Streamlit |
| Literature data | PubMed E-utilities (Biopython) |
| Trend data | Google Trends (pytrends) |
| AI synthesis | Anthropic Claude API |
| Charts | Plotly |
| PDF generation | fpdf2 |
| Database | Session-based (in-memory) |

---

## Citation

If you use MIRS in academic work, please cite:

> Pierri MDP. MIRS: Medical Intelligence Report System — An AI-augmented framework for evidence-perception gap analysis in medicine. 2026. Available at: https://github.com/micheledpierri/mirs-app

---

## License

This project is licensed under the MIT License — see below.

```
MIT License

Copyright (c) 2026 Michele Danilo Pierri

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Author

**Michele Danilo Pierri, MD, PhD**  
Cardiothoracic Surgeon · Medical Data Scientist  
[micheledpierri.com](https://micheledpierri.com)

*MIRS is developed as a research tool for the medical community. It is not intended to replace clinical judgment or peer-reviewed systematic reviews.*
