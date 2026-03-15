"""
MIRS — Configuration (Streamlit Web Version)

Reads credentials from Streamlit secrets (st.secrets) for deployment,
with fallback to environment variables for local development.

Streamlit secrets are configured in:
  - .streamlit/secrets.toml  (local)
  - Streamlit Cloud dashboard (production)
"""

import os

# ---------------------------------------------------------------------------
# Helper: read from Streamlit secrets first, then env var, then default
# ---------------------------------------------------------------------------

def _get_secret(key: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets or environment variables."""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# API Credentials
# ---------------------------------------------------------------------------

PUBMED_API_KEY = _get_secret("PUBMED_API_KEY")
PUBMED_EMAIL = _get_secret("PUBMED_EMAIL")
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")

# Validate at import time — but don't crash the whole app, just warn
_missing = []
if not PUBMED_API_KEY:
    _missing.append("PUBMED_API_KEY")
if not PUBMED_EMAIL:
    _missing.append("PUBMED_EMAIL")
if _missing:
    print(f"⚠ Missing secrets: {', '.join(_missing)}  — PubMed search will not work")

# ---------------------------------------------------------------------------
# App password for beta access
# ---------------------------------------------------------------------------

APP_PASSWORD = _get_secret("APP_PASSWORD", "")

# ---------------------------------------------------------------------------
# PubMed rate limits
# ---------------------------------------------------------------------------

REQUEST_DELAY = 0.34        # seconds between requests (~3 req/s safe)
DEFAULT_MAX_RESULTS = 100
DEFAULT_RETMAX = 20         # batch size for EFetch

# ---------------------------------------------------------------------------
# LLM settings
# ---------------------------------------------------------------------------

LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"
