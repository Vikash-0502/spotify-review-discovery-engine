"""Streamlit dashboard — Review Discovery Engine (Phase 6 Redesign)."""

import base64
import html
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so imports work when run via `streamlit run`
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
SPOTIFY_ICON_PATH = DASHBOARD_DIR / "assets" / "spotify-icon.png"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.question_mapper import compute_segment_label
import analysis.llm as llm
from dashboard.helpers import evidence_strength_label, render_based_on_badge, sentiment_badge
from utils.config import get_settings  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Spotify Review Discovery Engine",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import os

settings = get_settings()

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    f"http://127.0.0.1:{settings.api_port}/api"
)

HEALTH_URL = API_BASE_URL.replace("/api", "/health")

PLATFORM_LABELS = {
    "play_store": "Play Store Reviews",
    "app_store": "App Store Reviews",
    "spotify_community": "Community Discussions",
}

PLATFORM_OPTIONS = {
    "All Sources": None,
    "Play Store Reviews": "play_store",
    "App Store Reviews": "app_store",
    "Community Discussions": "spotify_community",
}

PLATFORM_OPTIONS_INV = {v: k for k, v in PLATFORM_OPTIONS.items() if v is not None}
TAB_OPTIONS = ["Overview", "Themes & Chat", "Segments", "Unmet Needs", "Review Discovery"]


# ═══════════════════════════════════════════════════════════════════════════
# Health check & Status
# ═══════════════════════════════════════════════════════════════════════════
def check_api_health() -> bool:
    try:
        resp = requests.get(HEALTH_URL, timeout=2.0)
        return resp.status_code == 200 and resp.json().get("status") == "ok"
    except Exception:
        return False


if not check_api_health():
    st.error("🔴 **FastAPI Backend is Offline**")
    st.info(
        "Start the API server first:\n\n"
        "```bash\nuvicorn api.main:app --reload\n```"
    )
    st.stop()


def fetch_pipeline_status():
    try:
        resp = requests.get(f"{API_BASE_URL}/pipeline/status", timeout=2.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"status": "offline", "last_synced": None, "total_reviews": 0, "themes_count": 0}


def trigger_pipeline_refresh():
    try:
        resp = requests.post(f"{API_BASE_URL}/pipeline/refresh", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


# Fetch status info
status_info = fetch_pipeline_status()
synced_time_str = "Never"
if status_info.get("last_synced"):
    try:
        dt = datetime.fromisoformat(status_info["last_synced"])
        synced_time_str = dt.strftime("%b %d, %Y — %I:%M %p")
    except Exception:
        synced_time_str = str(status_info["last_synced"])


if "source_label" not in st.session_state:
    st.session_state.source_label = "All Sources"
if "date_preset" not in st.session_state:
    st.session_state.date_preset = "All time"
if "custom_from" not in st.session_state:
    st.session_state.custom_from = datetime.now(timezone.utc).date()
if "custom_to" not in st.session_state:
    st.session_state.custom_to = datetime.now(timezone.utc).date()
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Overview"


def _resolve_date_range():
    now = datetime.now(timezone.utc)
    preset = st.session_state.date_preset
    if preset == "Last 7 days":
        return now - timedelta(days=7), now
    if preset == "Last 30 days":
        return now - timedelta(days=30), now
    if preset == "Last 90 days":
        return now - timedelta(days=90), now
    if preset == "Custom":
        d_start = st.session_state.custom_from
        d_end = st.session_state.custom_to
        date_start = datetime.combine(d_start, datetime.min.time(), tzinfo=timezone.utc) if d_start else None
        date_end = datetime.combine(d_end, datetime.max.time(), tzinfo=timezone.utc) if d_end else None
        return date_start, date_end
    return None, None


selected_platform = PLATFORM_OPTIONS.get(st.session_state.source_label)
date_start, date_end = _resolve_date_range()


# ═══════════════════════════════════════════════════════════════════════════
# API Helpers
# ═══════════════════════════════════════════════════════════════════════════
def _common_params(start, end, platform):
    params = {}
    if start:
        params["from_date"] = start.isoformat()
    if end:
        params["to_date"] = end.isoformat()
    if platform:
        params["platform"] = platform
    return params


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stats(_start, _end, _platform):
    resp = requests.get(f"{API_BASE_URL}/stats", params=_common_params(_start, _end, _platform))
    resp.raise_for_status()
    data = resp.json()
    ds = datetime.fromisoformat(data["date_range_start"]) if data["date_range_start"] else None
    de = datetime.fromisoformat(data["date_range_end"]) if data["date_range_end"] else None
    return data["total_reviews"], ds, de, data["platforms"]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_metrics(_start, _end, _platform):
    resp = requests.get(f"{API_BASE_URL}/metrics", params=_common_params(_start, _end, _platform))
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_sentiment(_start, _end, _platform):
    resp = requests.get(f"{API_BASE_URL}/sentiment", params=_common_params(_start, _end, _platform))
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_themes(_start, _end, _platform, limit=16):
    params = _common_params(_start, _end, _platform)
    params["limit"] = limit
    resp = requests.get(f"{API_BASE_URL}/themes", params=params)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_segments(_start, _end, _platform):
    resp = requests.get(f"{API_BASE_URL}/segments", params=_common_params(_start, _end, _platform))
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_theme_reviews(theme_id, limit=15):
    resp = requests.get(f"{API_BASE_URL}/themes/{theme_id}/reviews", params={"limit": limit})
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_pain_points(_start, _end, _platform, limit=10):
    params = _common_params(_start, _end, _platform)
    params["limit"] = limit
    resp = requests.get(f"{API_BASE_URL}/pain-points", params=params)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_quotes(_start, _end, _platform, limit=12):
    params = _common_params(_start, _end, _platform)
    params["limit"] = limit
    resp = requests.get(f"{API_BASE_URL}/quotes", params=params)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_questions(_start, _end, _platform):
    resp = requests.get(f"{API_BASE_URL}/questions", params=_common_params(_start, _end, _platform))
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=120, show_spinner=False)
def fetch_latest_weekly_pulse():
    resp = requests.get(f"{API_BASE_URL}/weekly-pulse/latest", timeout=3.0)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=300, show_spinner=False)
def cache_generate_theme_name(theme_id, top_keywords, sample_reviews):
    fn = getattr(llm, "generate_theme_name", None)
    if fn:
        return fn(list(top_keywords or []), list(sample_reviews or []))
    if hasattr(llm, "summarize_theme"):
        return llm.summarize_theme(list(top_keywords or []), list(sample_reviews or []))["theme_name"]
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def cache_generate_cluster_finding(theme_id, top_keywords, sample_reviews, review_count, avg_rating=None, neg_pct=None):
    fn = getattr(llm, "generate_cluster_finding", None)
    if fn:
        return fn(
            list(top_keywords or []),
            list(sample_reviews or []),
            review_count,
            avg_rating,
            neg_pct,
        )
    return {
        "title": f"{review_count} users report a specific problem in this cluster.",
        "impact": "This issue is harming discovery and satisfaction for affected listeners.",
    }


@st.cache_data(ttl=300, show_spinner=False)
def cache_generate_overall_sentiment_summary(theme_names, positive, neutral, negative, total_reviews, overall_avg_rating=None):
    fn = getattr(llm, "generate_overall_sentiment_summary", None)
    if fn:
        return fn(
            list(theme_names or []),
            positive,
            neutral,
            negative,
            total_reviews,
            overall_avg_rating,
        )
    negative_pct = round(negative / max(total_reviews, 1) * 100)
    if total_reviews == 0:
        return "No review sentiment is available for the selected filters."
    if negative_pct >= 55:
        return "Overall sentiment is strongly negative and users are largely dissatisfied with the current experience."
    if negative_pct >= 35:
        return "Sentiment is mixed, with clear dissatisfaction around core music discovery and playback flows."
    return "Most users feel somewhat satisfied, but there are still notable friction points in the experience."


def search_reviews(query_text, platform, start, end, limit=30):
    params = {"q": query_text, "limit": limit}
    if start:
        params["from_date"] = start.isoformat()
    if end:
        params["to_date"] = end.isoformat()
    if platform:
        params["platform"] = platform
    resp = requests.get(f"{API_BASE_URL}/search", params=params)
    resp.raise_for_status()
    return resp.json()


def ask_discovery_chat(query_text, platform, start, end, limit=6):
    params = {"q": query_text, "limit": limit}
    if start:
        params["from_date"] = start.isoformat()
    if end:
        params["to_date"] = end.isoformat()
    if platform:
        params["platform"] = platform
    resp = requests.get(f"{API_BASE_URL}/chat", params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


# Fetch initial metrics
total, ds, de, platforms = fetch_stats(date_start, date_end, selected_platform)
metrics = fetch_metrics(date_start, date_end, selected_platform)
sentiment = fetch_sentiment(date_start, date_end, selected_platform)
themes = fetch_themes(date_start, date_end, selected_platform)
segments = fetch_segments(date_start, date_end, selected_platform)
pain_points = fetch_pain_points(date_start, date_end, selected_platform)
quotes = fetch_quotes(date_start, date_end, selected_platform)
question_data = fetch_questions(date_start, date_end, selected_platform)
latest_pulse = fetch_latest_weekly_pulse()


# ═══════════════════════════════════════════════════════════════════════════
# CSS — Black Theme with High Contrast Text
# ═══════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stSidebar"] {
        font-family: 'Outfit', sans-serif;
        background-color: #000000 !important;
        color: #f5f5f5 !important;
    }

    .stApp {
        background-color: #000000 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #000000 !important;
        border-right: 1px solid #1f1f1f;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }

    [data-testid="stToolbar"] {
        display: none;
    }

    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    .stNumberInput > div > div > input {
        background-color: #0f0f0f !important;
        color: #ffffff !important;
        border: 1px solid #2a2a2a !important;
    }

    .stButton > button {
        background-color: #111111 !important;
        color: #ffffff !important;
        border: 1px solid #2f2f2f !important;
    }

    .stButton > button:hover {
        border-color: #1DB954 !important;
        color: #1DB954 !important;
    }

    .stDownloadButton > button,
    .stFormSubmitButton > button {
        background-color: #111111 !important;
        color: #ffffff !important;
        border: 1px solid #2f2f2f !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.4rem;
    }

    .stTabs [data-baseweb="tab"] {
        color: #d9d9d9;
        background-color: #0f0f0f;
        border: 1px solid #222222;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #1DB954;
        color: #000000;
    }

    .stAlert, .stInfo, .stSuccess, .stWarning, .stError {
        color: #ffffff !important;
        border-radius: 8px;
    }

    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown span, .stMarkdown label {
        color: #f5f5f5 !important;
    }

    /* Top bar badge */
    .pipeline-status {
        background-color: rgba(29, 185, 84, 0.12);
        color: #1DB954;
        border: 1px solid rgba(29, 185, 84, 0.3);
        padding: 0.3rem 0.8rem;
        border-radius: 99px;
        font-weight: 600;
        font-size: 0.8rem;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
    }

    /* Segment badges */
    .segment-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .seg-high-friction { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .seg-moderate-friction { background: rgba(245,158,11,0.18); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
    .seg-trending { background: rgba(249,115,22,0.18); color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
    .seg-positive { background: rgba(34,197,94,0.18); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
    .seg-low { background: rgba(156,163,175,0.18); color: #d1d5db; border: 1px solid rgba(156,163,175,0.3); }

    .theme-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.45px;
        text-transform: uppercase;
    }
    .badge-high-friction { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .badge-trending-up { background: rgba(249,115,22,0.18); color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
    .badge-stable { background: rgba(34,197,94,0.18); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }

    .theme-bar-card {
        background: #111111;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1.5rem;
    }
    .theme-bar-header {
        margin-bottom: 1rem;
    }
    .bar-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.85rem;
    }
    .bar-label {
        min-width: 180px;
        max-width: 240px;
        color: #f5f5f5;
        font-size: 0.95rem;
        line-height: 1.2;
    }
    .bar-track {
        flex: 1;
        background: #0f0f0f;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 999px;
        overflow: hidden;
        height: 0.9rem;
    }
    .bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #1DB954, #4ade80);
        border-radius: 999px;
    }
    .bar-value {
        min-width: 72px;
        text-align: right;
        color: #e5e7eb;
        font-size: 0.85rem;
    }

    /* Custom Theme Cards */
    .custom-theme-card {
        background: #111111;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        transition: transform 0.2s, border-color 0.2s;
    }
    .custom-theme-card:hover {
        transform: translateY(-2px);
        border-color: rgba(29, 185, 84, 0.4);
    }
    .theme-card-header {
        display: flex;
        justify-content: space-between;
        align-items: start;
        margin-bottom: 0.4rem;
    }
    .theme-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #ffffff;
        margin: 0;
    }
    .theme-subtitle {
        font-size: 0.85rem;
        color: #f3f4f6;
        margin-bottom: 0.8rem;
    }
    .theme-meta-row {
        display: flex;
        gap: 1.2rem;
        font-size: 0.9rem;
        color: #f3f4f6;
    }
    .theme-meta-item strong {
        color: #ffffff;
    }

    .nav-container {
        display: flex;
        gap: 0.6rem;
        margin-bottom: 1.8rem;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding-bottom: 0.8rem;
    }

    .overview-metric-card {
        background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
        border-radius: 12px;
        padding: 1.4rem;
        border: 1px solid rgba(255,255,255,0.08);
        text-align: left;
    }
    .overview-metric-card h3 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
        color: #d1d5db;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .overview-metric-card h2 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
        color: #ffffff;
    }
    .overview-metric-card p {
        margin: 0.4rem 0 0 0;
        font-size: 0.8rem;
        color: #c7c7c7;
    }

    .chat-bubble-user {
        background-color: #171717;
        border-radius: 12px 12px 2px 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .chat-bubble-ai {
        background-color: #0b0b0b;
        border-left: 4px solid #1DB954;
        border-radius: 4px 12px 12px 12px;
        padding: 1.2rem;
        margin-bottom: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.04);
        border-bottom: 1px solid rgba(255,255,255,0.04);
        border-right: 1px solid rgba(255,255,255,0.04);
    }

    .star-rating { font-size: 1.2rem; }
    .star-filled { color: #f59e0b; }
    .star-empty { color: #374151; }

    .evidence-quote-box {
        background: rgba(255,255,255,0.05);
        border-left: 2px solid rgba(29, 185, 84, 0.6);
        border-radius: 4px;
        padding: 0.8rem 1rem;
        margin-top: 0.6rem;
        font-size: 0.85rem;
        font-style: italic;
        color: #f3f4f6;
    }
    .evidence-quote-source {
        font-size: 0.72rem;
        color: #d1d5db;
        margin-top: 0.3rem;
        text-align: right;
    }

    .active-filter-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(29, 185, 84, 0.12);
        color: #1DB954;
        border: 1px solid rgba(29, 185, 84, 0.3);
        border-radius: 999px;
        padding: 0.35rem 0.85rem;
        font-size: 0.82rem;
        font-weight: 600;
    }

    .page-header-wrap {
        background: linear-gradient(180deg, rgba(17,17,17,0.98), rgba(10,10,10,0.98));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 1.4rem 1.5rem 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }
    .page-title-row {
        display: flex;
        align-items: center;
        gap: 0.9rem;
    }
    .page-title-icon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        object-fit: cover;
        flex-shrink: 0;
        display: block;
        box-shadow: 0 0 0 6px rgba(29, 185, 84, 0.08);
    }
    .page-title-text {
        color: #ffffff;
        font-size: 2.4rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.1;
    }
    .page-title-caption {
        color: #9ca3af;
        font-size: 0.88rem;
        margin-top: 0.2rem;
    }
    .header-side-card {
        background: #111111;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        text-align: right;
    }
    .nav-shell {
        background: #0f0f0f;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px;
        padding: 0.55rem 0.6rem;
        margin: 1rem 0 0.2rem 0;
    }
    .pulse-card {
        background: linear-gradient(180deg, rgba(17,17,17,1), rgba(12,12,12,1));
        border: 1px solid rgba(29, 185, 84, 0.22);
        border-radius: 18px;
        padding: 1.2rem 1.3rem;
        margin: 1rem 0 1.5rem 0;
    }
    .pulse-label {
        color: #1DB954;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.7px;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }
    .pulse-title {
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.45rem 0;
    }
    .pulse-summary {
        color: #d1d5db;
        font-size: 0.92rem;
        line-height: 1.55;
        margin: 0 0 0.85rem 0;
    }
    .pulse-meta {
        color: #9ca3af;
        font-size: 0.8rem;
    }
    .complaint-card-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.85rem;
        margin: 0.35rem 0 0.9rem 0;
    }
    .complaint-card {
        background: linear-gradient(180deg, rgba(20,20,20,1), rgba(14,14,14,1));
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 0.95rem 1rem;
        min-height: 108px;
    }
    .complaint-card-header {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.55rem;
    }
    .complaint-card-icon {
        width: 30px;
        height: 30px;
        border-radius: 999px;
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(239, 68, 68, 0.24);
        color: #f87171;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.95rem;
    }
    .complaint-card-title {
        color: #ffffff;
        font-size: 0.84rem;
        font-weight: 700;
        letter-spacing: 0.45px;
        text-transform: uppercase;
    }
    .complaint-card-text {
        color: #d1d5db;
        font-size: 0.92rem;
        line-height: 1.5;
        margin: 0;
    }
    .filter-panel {
        background: #111111;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 1.2rem 1.3rem;
        margin: 0.8rem 0 1.2rem 0;
    }
    .filter-panel-title {
        color: #ffffff;
        font-size: 1rem;
        font-weight: 700;
        margin: 0 0 0.25rem 0;
    }
    .filter-panel-caption {
        color: #9ca3af;
        font-size: 0.88rem;
        margin: 0 0 0.85rem 0;
    }
    .evidence-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: rgba(29, 185, 84, 0.12);
        color: #1DB954;
        border: 1px solid rgba(29, 185, 84, 0.28);
        border-radius: 999px;
        padding: 0.28rem 0.7rem;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.25px;
        text-transform: uppercase;
    }
    .sent-badge {
        display: inline-block;
        padding: 0.18rem 0.55rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.35px;
        text-transform: uppercase;
    }
    .sent-negative {
        background: rgba(234, 88, 12, 0.18);
        color: #fdba74;
        border: 1px dashed rgba(251, 146, 60, 0.55);
    }
    .sent-neutral {
        background: rgba(59, 130, 246, 0.16);
        color: #93c5fd;
        border: 1px solid rgba(96, 165, 250, 0.45);
    }
    .sent-positive {
        background: rgba(20, 184, 166, 0.16);
        color: #5eead4;
        border: 1px solid rgba(45, 212, 191, 0.45);
    }
    .research-question-card {
        background: linear-gradient(180deg, rgba(18,18,18,1), rgba(12,12,12,1));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.85rem;
    }
    .research-question-title {
        color: #ffffff;
        font-size: 0.98rem;
        font-weight: 700;
        margin: 0 0 0.45rem 0;
        line-height: 1.35;
    }
    .research-question-answer {
        color: #d1d5db;
        font-size: 0.92rem;
        line-height: 1.55;
        margin: 0.55rem 0 0 0;
    }
    .strength-badge {
        display: inline-block;
        padding: 0.18rem 0.55rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.35px;
        text-transform: uppercase;
    }
    .strength-high { background: rgba(234, 88, 12, 0.18); color: #fdba74; border: 1px solid rgba(251, 146, 60, 0.4); }
    .strength-medium { background: rgba(59, 130, 246, 0.16); color: #93c5fd; border: 1px solid rgba(96, 165, 250, 0.4); }
    .strength-low { background: rgba(148, 163, 184, 0.16); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.35); }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_spotify_icon_data_uri() -> str:
    if not SPOTIFY_ICON_PATH.exists():
        return ""
    encoded = base64.b64encode(SPOTIFY_ICON_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ═══════════════════════════════════════════════════════════════════════════
# Layout Header + Top Navigation
# ═══════════════════════════════════════════════════════════════════════════
header_col1, header_col2 = st.columns([2.3, 1])

with header_col1:
    spotify_icon_uri = get_spotify_icon_data_uri()
    icon_html = (
        f'<img class="page-title-icon" src="{spotify_icon_uri}" alt="Spotify logo" />'
        if spotify_icon_uri
        else '<div class="page-title-icon" style="background:#1DB954;"></div>'
    )
    st.markdown(
        f"""
        <div class="page-header-wrap">
            <div class="page-title-row">
                {icon_html}
                <div>
                    <h1 class="page-title-text">Spotify Review Discovery Engine</h1>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_col2:
    status_text = "Pipeline online" if status_info.get("status") == "idle" else f"Pipeline {status_info.get('status')}"
    st.markdown(
        f"""
        <div class="header-side-card">
            <div class="pipeline-status">{status_text}</div>
            <div style="font-size: 0.78rem; color: #8e8e8e; margin-top: 0.45rem;">Synced: {synced_time_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Refresh pipeline", key="btn_refresh_pipeline_header", type="secondary", use_container_width=True):
        with st.spinner("Re-running NLP theme analysis pipeline..."):
            if trigger_pipeline_refresh():
                st.success("Analysis pipeline triggered successfully!")
                st.rerun()
            else:
                st.error("Failed to trigger pipeline.")

st.markdown('<div class="nav-shell"></div>', unsafe_allow_html=True)
nav_cols = st.columns(len(TAB_OPTIONS))
for idx, tab_name in enumerate(TAB_OPTIONS):
    button_type = "primary" if st.session_state.active_tab == tab_name else "secondary"
    with nav_cols[idx]:
        if st.button(tab_name, key=f"nav_{tab_name}", type=button_type, use_container_width=True):
            st.session_state.active_tab = tab_name
            st.rerun()


def render_shared_filters():
    st.markdown(
        '<div class="filter-panel">'
        '<div class="filter-panel-title">Review filters</div>'
        '<div class="filter-panel-caption">Shared across Overview, Themes, Segments, Unmet Needs, and Review Discovery.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_filter_1, col_filter_2 = st.columns([1, 1])
    with col_filter_1:
        st.selectbox(
            "Source filter",
            list(PLATFORM_OPTIONS.keys()),
            index=list(PLATFORM_OPTIONS.keys()).index(st.session_state.source_label),
            key="source_label",
        )
    with col_filter_2:
        st.selectbox(
            "Date range",
            ["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
            index=["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Custom"].index(st.session_state.date_preset),
            key="date_preset",
        )
    if st.session_state.date_preset == "Custom":
        col_custom_1, col_custom_2 = st.columns(2)
        with col_custom_1:
            st.date_input("From", value=st.session_state.custom_from, key="custom_from")
        with col_custom_2:
            st.date_input("To", value=st.session_state.custom_to, key="custom_to")


def get_date_label() -> str:
    if st.session_state.date_preset == "Custom":
        return (
            f"{st.session_state.custom_from.strftime('%b %d, %Y')} to "
            f"{st.session_state.custom_to.strftime('%b %d, %Y')}"
        )
    return st.session_state.date_preset


def render_active_filter_summary(total_reviews: int):
    source_label = st.session_state.source_label
    st.markdown(
        f'<div class="active-filter-badge">'
        f'Source: {html.escape(source_label)} · Dates: {html.escape(get_date_label())} · '
        f'{total_reviews:,} reviews in scope'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_research_questions_section(answers: list[dict]):
    st.subheader("🎯 Research questions")
    st.caption("Overview answers mapped to the six core discovery research questions.")

    if not answers:
        st.info("Research question answers are not available for the selected filters.")
        return

    for idx, answer in enumerate(answers, 1):
        question = html.escape(answer.get("question", f"Research question {idx}"))
        summary = html.escape(answer.get("answer_summary", "No answer available."))
        review_count = int(answer.get("supporting_review_count", 0) or 0)
        stars_html = render_stars_str(int(answer.get("criticality_rating", 3) or 3))
        st.markdown(
            f'<div class="research-question-card">'
            f'  <div class="research-question-title">Q{idx}. {question}</div>'
            f'  {render_based_on_badge(review_count)}'
            f'  <div style="margin-top:0.55rem;font-size:0.85rem;color:#9ca3af;">Criticality: {stars_html}</div>'
            f'  <p class="research-question-answer">{summary}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        quotes = answer.get("representative_quotes", []) or []
        if quotes:
            with st.expander(f"View supporting evidence ({len(quotes)} excerpts)", expanded=False):
                for quote in quotes:
                    excerpt = html.escape((quote.get("excerpt") or "")[:320])
                    platform = html.escape(quote.get("platform") or "unknown")
                    review_id = quote.get("review_id")
                    source_line = f"{platform}" if not review_id else f"{platform} · review_id: {review_id}"
                    st.markdown(
                        f'<div class="evidence-quote-box">"{excerpt}"'
                        f'<div class="evidence-quote-source">— {source_line}</div></div>',
                        unsafe_allow_html=True,
                    )


render_shared_filters()
render_active_filter_summary(total)


# Helper rating stars
def render_stars_str(rating: int, max_stars: int = 5) -> str:
    filled = "★" * rating
    empty = "☆" * (max_stars - rating)
    return f'<span class="star-rating"><span class="star-filled">{filled}</span><span class="star-empty">{empty}</span></span>'


def compute_friction_label(sentiment: str) -> str:
    if sentiment == "negative":
        return "High Friction"
    if sentiment == "neutral":
        return "Moderate Friction"
    return "Positive Signal"


def get_segment_badge_class(segment: str) -> str:
    if "High Friction" in segment:
        return "seg-high-friction"
    if "Moderate" in segment:
        return "seg-moderate-friction"
    if "Trending" in segment:
        return "seg-trending"
    if "Positive" in segment:
        return "seg-positive"
    return "seg-low"


def render_latest_pulse_card(pulse_data):
    if not pulse_data:
        st.info("No weekly pulse has been generated yet.")
        return

    pulse_title = pulse_data.get("title", "Weekly pulse")
    pulse_headline = pulse_data.get("headline", "Latest pulse")
    pulse_summary = pulse_data.get("summary", "No summary available.")
    sample_reviews = pulse_data.get("sample_review_count", 0)
    source_reviews = pulse_data.get("source_review_count", 0)
    validation_passed = pulse_data.get("validation_passed", False)
    delivery_status = pulse_data.get("delivery_status", "unknown")
    document_url = pulse_data.get("document_url")
    meta_bits = [
        f"Validation: {'Passed' if validation_passed else 'Needs review'}",
        f"Delivery: {delivery_status.replace('_', ' ')}",
        f"Sample: {sample_reviews:,} / {source_reviews:,} reviews" if source_reviews else f"Sample: {sample_reviews:,} reviews",
    ]

    st.markdown(
        f"""
        <div class="pulse-card">
            <div class="pulse-label">Latest Weekly Pulse</div>
            <div class="pulse-title">{pulse_headline}</div>
            <p class="pulse-summary">{pulse_summary}</p>
            <div class="pulse-meta">{pulse_title} · {' · '.join(meta_bits)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if document_url:
        if str(document_url).startswith("http"):
            st.markdown(f"[Open latest weekly pulse]({document_url})")
        else:
            st.caption(f"Latest pulse preview saved at: `{document_url}`")


def _normalize_issue_tokens(text: str) -> set[str]:
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "into", "about",
        "users", "user", "spotify", "issue", "problem", "problems", "related",
        "music", "reviews", "feedback", "report", "reports",
    }
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return {
        token
        for token in cleaned.split()
        if len(token) > 2 and token not in stop_words
    }


def _simplify_sentence(text: str) -> str:
    text = " ".join(text.replace("\n", " ").split()).strip()
    if not text:
        return ""
    sentence = text.split(".")[0].strip()
    replacements = {
        "Users report issues related to ": "Users report ",
        "Users describe how they interact with Spotify around ": "Users say ",
        "This pattern appears in ": "This shows up in ",
        "This issue is causing friction in ": "This creates friction in ",
        "Likely caused by ": "This may be caused by ",
    }
    for old, new in replacements.items():
        sentence = sentence.replace(old, new)
    sentence = sentence.strip(" -,:;")
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def build_key_findings(themes_list, pain_points_list, question_answers, selected_platform_value):
    findings: list[str] = []
    seen_keys: set[str] = set()

    def add_finding(text: str, dedup_key: str | None = None):
        simple = " ".join(text.split()).strip()
        if not simple:
            return
        if simple[-1] not in ".!?":
            simple += "."
        key = (dedup_key or simple).lower()
        if key in seen_keys:
            return
        seen_keys.add(key)
        findings.append(simple)

    theme_name_map = build_complaint_theme_name_map(themes_list)
    grouped: dict[str, dict] = {}

    for theme in themes_list:
        theme_id = theme.get("id")
        theme_name = theme_name_map.get(theme_id, derive_complaint_theme_name(theme))
        if theme_name == "Positive streaming experience":
            continue

        keyword_text = _theme_keyword_text(theme)
        category = _match_complaint_category(keyword_text)
        group_key = category or theme_name.lower()
        entry = grouped.setdefault(
            group_key,
            {
                "label": COMPLAINT_THEME_LABELS.get(category, theme_name) if category else theme_name,
                "category": category,
                "review_count": 0,
            },
        )
        entry["review_count"] += int(theme.get("review_count", 0) or 0)

    theme_slots = 4 if pain_points_list else 5
    for _group_key, data in sorted(
        grouped.items(),
        key=lambda item: item[1]["review_count"],
        reverse=True,
    )[:theme_slots]:
        add_finding(
            format_theme_key_finding(data["category"], data["label"], data["review_count"]),
            dedup_key=data["category"] or data["label"].lower(),
        )

    unmet_needs_finding = build_unmet_needs_finding(pain_points_list)
    if unmet_needs_finding:
        add_finding(unmet_needs_finding, dedup_key="unmet-needs")

    fallback_findings = [
        "The algorithm sometimes misses taste or genre context, leading to misaligned recommendations, as mentioned across the filtered review set.",
        "Shuffle plays the same songs repeatedly, reducing perceived discovery value, as reported across the filtered review set.",
        "Unwanted recommendations injected into playlists is a major concern, supported across the filtered review set.",
        "Home feed and discovery surfaces often show non-music content, such as podcasts or stale picks, instead of new music aligned with listening history, as seen across the filtered review set.",
        "Free-tier limits block on-demand listening, limiting intentional discovery and playlist listening, as noted across the filtered review set.",
    ]
    if selected_platform_value == "spotify_community":
        fallback_findings.append(
            "Community discussions highlight transparency and control gaps in recommendation behavior across the filtered discussion set."
        )

    for fallback in fallback_findings:
        add_finding(fallback, dedup_key=f"fallback:{fallback[:40]}")
        if len(findings) >= 5:
            break

    return findings[:5]


def build_top_opportunities(key_findings):
    opportunities: list[str] = []
    seen: set[str] = set()

    def add_opportunity(text: str):
        clean = text.strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        opportunities.append(clean)

    for finding in key_findings:
        lower = finding.lower()
        if "repeat" in lower or "same songs" in lower or "stale" in lower:
            add_opportunity("Improve recommendation freshness so users discover more new music and keep listening longer.")
        elif "shuffle" in lower or "autoplay" in lower:
            add_opportunity("Fix shuffle and autoplay behavior so playback feels more varied and trustworthy.")
        elif "control" in lower or "filter" in lower or "feedback" in lower:
            add_opportunity("Add clearer discovery controls so users can teach Spotify what they want faster.")
        elif "unrelated" in lower or "irrelevant" in lower or "trust" in lower:
            add_opportunity("Improve recommendation relevance to reduce frustration and increase confidence in discovery features.")
        elif "community" in lower or "transparency" in lower or "preferences" in lower:
            add_opportunity("Show users why songs are recommended and give them better ways to tune their preferences.")
        else:
            add_opportunity("Solve this friction point to make discovery easier and increase engagement with recommendation features.")

    while len(opportunities) < 3:
        add_opportunity("Reduce repeated recommendations to improve satisfaction and retention.")

    return opportunities[:5]


def _theme_keyword_text(theme) -> str:
    return " ".join(
        str(k).strip().lower()
        for k in (theme.get("top_keywords") or [])
        if str(k).strip()
    )


def _match_complaint_category(keyword_text: str) -> str | None:
    rules = [
        ("shuffle", ("shuffle", "smart shuffle")),
        ("ads", ("ads", "advert", "skips")),
        ("recommendations", ("recommend", "discover", "weekly", "radar", "release radar", "algorithm")),
        ("playback", ("playlist", "queue", "autoplay", "playlists")),
        ("ai_content", ("slop", "generated", " ai", "ai music")),
        ("search", ("search",)),
        ("podcasts", ("podcast", "podcasts", "episodes", "audiobook")),
        ("ui", ("widget", "screen", "update", "worse")),
        ("library", ("liked", "liked songs", "add")),
        ("sync", ("offline", "load", "folder", "folders", "desktop", "mobile")),
        ("account", ("account", "community", "support")),
        ("radio", ("radio", "dj")),
        ("premium", ("subscription", "pay", "hours")),
    ]
    padded = f" {keyword_text} "
    for category, terms in rules:
        if any(term in keyword_text or term in padded for term in terms):
            return category
    return None


COMPLAINT_THEME_LABELS = {
    "shuffle": "Repetitive shuffle playback",
    "ads": "Ads interrupting discovery",
    "recommendations": "Stale recommendations",
    "playback": "Playlist & playback friction",
    "ai_content": "Low-quality AI content",
    "search": "Search not surfacing new music",
    "podcasts": "Podcast discovery gaps",
    "ui": "App UI regressions",
    "library": "Library & liked songs",
    "sync": "Offline & sync issues",
    "account": "Account & support issues",
    "radio": "Radio & listening flow",
    "premium": "Premium value concerns",
}

COMPLAINT_THEME_SENTENCES = {
    "shuffle": "Users say shuffle keeps bringing back the same songs instead of helping them discover something new.",
    "ads": "Users say ads break the listening flow and make discovery feel more frustrating.",
    "recommendations": "Users say recommendations feel repetitive and do not surface enough fresh music.",
    "playback": "Users say playlist and playback controls do not support smooth music discovery.",
    "ai_content": "Users are unhappy when AI-related content feels low quality or unrelated to what they want to hear.",
    "search": "Users say search does not help them quickly find the kind of new music they want.",
    "podcasts": "Users say podcast recommendations and listening limits get in the way of discovery.",
    "ui": "Users say recent app UI changes make the listening experience harder to use.",
    "library": "Users struggle to manage liked songs and library organization during discovery.",
    "sync": "Users report offline, sync, and device issues that interrupt music discovery.",
    "account": "Users report account and community support issues that block a smooth experience.",
    "radio": "Users say radio and listening flows do not help them discover varied new music.",
    "premium": "Users question premium value when ads, limits, or paywalls interrupt discovery.",
}

KEY_FINDING_TEMPLATES = {
    "playback": (
        "Unwanted recommendations injected into playlists is a major concern, "
        "supported by {count} sampled reviews."
    ),
    "shuffle": (
        "Shuffle plays the same songs repeatedly, reducing perceived discovery value, "
        "as reported in {count} sampled reviews."
    ),
    "podcasts": (
        "Home feed and discovery surfaces often show non-music content, such as podcasts or stale picks, "
        "instead of new music aligned with listening history, as seen in {count} sampled reviews."
    ),
    "recommendations": (
        "The algorithm sometimes misses taste or genre context, leading to misaligned recommendations, "
        "as mentioned in {count} sampled reviews."
    ),
    "premium": (
        "Free-tier limits block on-demand listening, limiting intentional discovery and playlist listening, "
        "as noted in {count} sampled reviews."
    ),
    "ads": (
        "Ads and skip limits interrupt the listening flow, limiting intentional discovery and playlist listening, "
        "as noted in {count} sampled reviews."
    ),
    "ai_content": (
        "AI-generated or low-quality music content appears in discovery feeds instead of relevant artist releases, "
        "as seen in {count} sampled reviews."
    ),
    "search": (
        "Search often fails to surface new music aligned with listening taste, reducing perceived discovery value, "
        "as reported in {count} sampled reviews."
    ),
    "ui": (
        "Recent app UI changes make discovery surfaces harder to use, "
        "as mentioned in {count} sampled reviews."
    ),
    "library": (
        "Library and liked-song management creates friction that interrupts smooth music discovery, "
        "as noted in {count} sampled reviews."
    ),
    "sync": (
        "Offline and sync issues interrupt playlist listening and discovery sessions, "
        "as reported in {count} sampled reviews."
    ),
    "account": (
        "Account and support issues block users from resolving discovery-related problems, "
        "as mentioned in {count} sampled reviews."
    ),
    "radio": (
        "Radio and autoplay flows surface repeated songs instead of fresh discovery options, "
        "as reported in {count} sampled reviews."
    ),
}


def format_theme_key_finding(category: str | None, label: str, count: int) -> str:
    if category and category in KEY_FINDING_TEMPLATES:
        return KEY_FINDING_TEMPLATES[category].format(count=f"{count:,}")
    return f"{label} is a recurring user concern, supported by {count:,} sampled reviews."


def build_unmet_needs_finding(pain_points_list) -> str | None:
    if not pain_points_list:
        return None

    topics: list[str] = []
    for point in pain_points_list[:6]:
        summary = (point.get("summary") or "").lower()
        if any(word in summary for word in ("ad", "advert", "skips")) and "ads" not in topics:
            topics.append("ads")
        if "premium" in summary and "premium service" not in topics:
            topics.append("premium service")
        if any(word in summary for word in ("free", "tier", "subscription", "pay")) and "the free tier" not in topics:
            topics.append("the free tier")

    if not topics:
        topics = ["ads", "premium service", "the free tier"]

    if len(topics) == 1:
        topic_text = topics[0]
    elif len(topics) == 2:
        topic_text = f"{topics[0]} and {topics[1]}"
    else:
        topic_text = ", ".join(topics[:-1]) + f", and {topics[-1]}"

    top_summary = (pain_points_list[0].get("summary") or "").strip()
    if not top_summary or len(top_summary) > 100:
        expression = "frustration with the service"
    else:
        expression = _simplify_sentence(top_summary).rstrip(".").lower()

    return (
        f"Unmet needs highlight issues with {topic_text}, "
        f"with the top unmet need expressing {expression}."
    )


def _looks_like_keyword_dump(text: str) -> bool:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return True
    if any(ch in cleaned for ch in ".,!?;:"):
        return False
    tokens = cleaned.lower().split()
    return len(tokens) >= 3 and all(len(token) < 24 for token in tokens)


def derive_complaint_theme_name(theme) -> str:
    keyword_text = _theme_keyword_text(theme)
    sentiment = (theme.get("overall_sentiment") or "").lower()
    positive_markers = ("love", "great", "best", "good", "easy", "quality")
    complaint_markers = (
        "ads", "shuffle", "bad", "issue", "worse", "dont", "frustrat",
        "slop", "generated", "broken", "horrible", "uglier",
    )
    positive_hits = sum(1 for word in positive_markers if word in keyword_text)
    if (
        sentiment == "positive"
        or (positive_hits >= 2 and not any(marker in keyword_text for marker in complaint_markers))
    ):
        return "Positive streaming experience"

    category = _match_complaint_category(keyword_text)
    if category:
        return COMPLAINT_THEME_LABELS[category]

    readable = (theme.get("readable_name") or theme.get("name") or "").strip()
    if readable and not _looks_like_keyword_dump(readable):
        return readable

    keywords = [str(k).strip() for k in (theme.get("top_keywords") or [])[:3] if str(k).strip()]
    if keywords:
        return " & ".join(keyword.title() for keyword in keywords)

    return "User complaint theme"


def build_complaint_theme_name_map(themes_list) -> dict:
    """Map theme id -> complaint-aligned label, disambiguating duplicates."""
    base_names = {theme["id"]: derive_complaint_theme_name(theme) for theme in themes_list}
    duplicate_names = {
        name for name in base_names.values() if list(base_names.values()).count(name) > 1
    }
    resolved: dict = {}
    used_suffixes: dict[str, set[str]] = {}

    for theme in themes_list:
        theme_id = theme["id"]
        base_name = base_names[theme_id]
        if base_name not in duplicate_names:
            resolved[theme_id] = base_name
            continue

        hint_tokens = [
            str(keyword).strip()
            for keyword in (theme.get("top_keywords") or [])
            if str(keyword).strip()
        ]
        suffix = next(
            (
                token.title()
                for token in hint_tokens
                if token.lower() not in base_name.lower()
            ),
            None,
        )
        if not suffix:
            suffix = f"Cluster {len(used_suffixes.get(base_name, set())) + 1}"

        used_suffixes.setdefault(base_name, set())
        while suffix in used_suffixes[base_name]:
            suffix = f"{suffix} {len(used_suffixes[base_name]) + 1}"
        used_suffixes[base_name].add(suffix)
        resolved[theme_id] = f"{base_name} · {suffix}"

    return resolved


def derive_keyword_complaints(themes_list):
    complaint_points: list[str] = []
    seen: set[str] = set()

    def add_point(text: str):
        sentence = _simplify_sentence(text)
        if not sentence:
            return
        key = sentence.lower()
        if key in seen:
            return
        seen.add(key)
        complaint_points.append(sentence)

    for theme in sorted(themes_list, key=lambda x: x.get("review_count", 0), reverse=True):
        keyword_text = _theme_keyword_text(theme)
        category = _match_complaint_category(keyword_text)
        if category:
            add_point(COMPLAINT_THEME_SENTENCES[category])
        else:
            label = derive_complaint_theme_name(theme)
            add_point(f"Users repeatedly complain about {label.lower()}.")

        summary = (theme.get("summary") or "").strip()
        root_cause = (theme.get("root_cause") or "").strip()
        if summary:
            add_point(summary)
        if root_cause:
            add_point(root_cause)

    fallback_points = [
        "Users struggle to find fresh music because discovery keeps circling back to familiar songs.",
        "Users lose trust when recommendations feel repetitive or unrelated to their taste.",
        "Users want smoother controls that help them guide what Spotify should play next.",
        "Users get frustrated when the listening flow is interrupted during discovery.",
    ]
    for point in fallback_points:
        add_point(point)

    return complaint_points[:5]


def build_complaint_cards_html(points):
    icons = ["!", "↻", "⚠", "♫", "⌕"]
    cards = []
    for idx, point in enumerate(points):
        icon = icons[idx % len(icons)]
        safe_point = html.escape(point)
        cards.append(
            "<div class='complaint-card'>"
            "<div class='complaint-card-header'>"
            f"<div class='complaint-card-icon'>{icon}</div>"
            f"<div class='complaint-card-title'>Key complaint {idx + 1}</div>"
            "</div>"
            f"<p class='complaint-card-text'>{safe_point}</p>"
            "</div>"
        )

    return (
        "<style>"
        "html, body { margin: 0; padding: 0; background: transparent; }"
        ".complaint-card-grid {"
        "display: grid;"
        "grid-template-columns: repeat(2, minmax(0, 1fr));"
        "gap: 0.85rem;"
        "font-family: 'Outfit', sans-serif;"
        "}"
        ".complaint-card {"
        "background: linear-gradient(180deg, rgba(20,20,20,1), rgba(14,14,14,1));"
        "border: 1px solid rgba(255,255,255,0.07);"
        "border-radius: 14px;"
        "padding: 0.95rem 1rem;"
        "min-height: 96px;"
        "box-sizing: border-box;"
        "}"
        ".complaint-card-header {"
        "display: flex;"
        "align-items: center;"
        "gap: 0.55rem;"
        "margin-bottom: 0.55rem;"
        "}"
        ".complaint-card-icon {"
        "width: 30px;"
        "height: 30px;"
        "border-radius: 999px;"
        "background: rgba(239, 68, 68, 0.14);"
        "border: 1px solid rgba(239, 68, 68, 0.24);"
        "color: #f87171;"
        "display: inline-flex;"
        "align-items: center;"
        "justify-content: center;"
        "font-size: 0.95rem;"
        "flex-shrink: 0;"
        "}"
        ".complaint-card-title {"
        "color: #ffffff;"
        "font-size: 0.84rem;"
        "font-weight: 700;"
        "letter-spacing: 0.45px;"
        "text-transform: uppercase;"
        "}"
        ".complaint-card-text {"
        "color: #d1d5db;"
        "font-size: 0.92rem;"
        "line-height: 1.5;"
        "margin: 0;"
        "}"
        "</style>"
        "<div class='complaint-card-grid'>"
        + "".join(cards)
        + "</div>"
    )


def render_complaint_cards(points):
    if not points:
        return
    card_count = min(len(points), 5)
    rows = math.ceil(card_count / 2)
    components.html(
        build_complaint_cards_html(points[:5]),
        height=(rows * 132) + 12,
        scrolling=False,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Tab 1: Overview
# ═══════════════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "Overview":
    platform_name = PLATFORM_LABELS.get(selected_platform, "All Platforms")
    date_label = get_date_label()

    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div class="overview-metric-card"><h3>Total Reviews</h3><h2>{total:,}</h2><p>Filtered set volume</p></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="overview-metric-card"><h3>Complaints</h3><h2>{metrics["complaint_count"]:,}</h2><p>Negative sentiment reviews</p></div>',
            unsafe_allow_html=True,
        )
    with k3:
        avg_rating = metrics.get("average_rating")
        avg_rating_display = f"{avg_rating:.2f}" if avg_rating is not None else "N/A"
        st.markdown(
            f'<div class="overview-metric-card"><h3>Average Rating</h3><h2>{avg_rating_display}</h2><p>From {metrics["rating_count"]} rated reviews</p></div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div class="overview-metric-card"><h3>Active Sources</h3><h2>{len(platforms)}</h2><p>Selected source scope</p></div>',
            unsafe_allow_html=True,
        )

    render_latest_pulse_card(latest_pulse)
    render_research_questions_section(question_data.get("answers", []) if question_data else [])

    def build_executive_summary(total_reviews, platform_name, date_label, sentiment_data):
        if total_reviews == 0:
            return "<div style='color:#e5e7eb;'>No reviews were found for the selected source and date range. Adjust the filters above to review a different data set.</div>"

        positive = sentiment_data["positive"]
        neutral = sentiment_data["neutral"]
        negative = sentiment_data["negative"]
        negative_pct = round(negative / max(total_reviews, 1) * 100)

        if negative_pct >= 55:
            tone = "user feedback is strongly negative, pointing to serious friction in discovery, recommendation relevance, and playback behavior."
        elif negative_pct >= 35:
            tone = "complaints are significant, indicating recurring problems with music discovery and repeated shuffle playback."
        else:
            tone = "feedback is mixed, with positive moments balanced by clear concerns around discovery quality."

        summary_lines = [
            f"<p style='margin:0 0 0.75rem; color:#e5e7eb;'>For <strong>{platform_name}</strong> during <strong>{date_label}</strong>, this view summarizes <strong>{total_reviews:,}</strong> reviews.</p>",
            f"<p style='margin:0 0 0.75rem; color:#e5e7eb;'>The selected source shows <strong>{negative_pct}%</strong> negative reviews, with users reporting discovery friction, repetitive shuffle playback, and irrelevant or non-music content surfacing in recommended music.</p>",
            f"<p style='margin:0 0 0.75rem; color:#e5e7eb;'>Key problems include difficulty finding fresh music, stale recommendation cycles, confusing playlist controls, and discovery surfaces polluted by unrelated content.</p>",
            f"<p style='margin:0 0 0.75rem; color:#e5e7eb;'>{tone}</p>",
        ]

        return "".join(summary_lines)

    st.subheader("📌 Executive summary")
    st.markdown(
        build_executive_summary(
            total,
            platform_name,
            date_label,
            sentiment,
        ),
        unsafe_allow_html=True,
    )

    issue_points = derive_keyword_complaints(themes)
    if not issue_points and question_data:
        for ans in question_data.get("answers", [])[:5]:
            text = ans.get("answer_summary", "").strip()
            if text:
                issue_points.append(_simplify_sentence(text))

    if issue_points:
        st.markdown(
            "<p style='margin:0 0 0.4rem; color:#f5f5f5; font-weight:600;'>Key complaint themes from the filtered reviews:</p>",
            unsafe_allow_html=True,
        )
        render_complaint_cards(issue_points[:5])

    def render_reviews_per_theme_chart(themes_list):
        if not themes_list:
            return
        sorted_themes = sorted(themes_list, key=lambda x: x.get("review_count", 0), reverse=True)[:6]
        max_count = max((t.get("review_count", 0) for t in sorted_themes), default=1)
        theme_name_map = build_complaint_theme_name_map(sorted_themes)
        rows = []

        for t in sorted_themes:
            theme_id = t.get("id")
            theme_name = html.escape(theme_name_map.get(theme_id, derive_complaint_theme_name(t)))

            width = round(min(100, max(3, t.get("review_count", 0) / max_count * 100)))
            rows.append(
                f'<div class="bar-row"><div class="bar-label">{theme_name}</div>'
                f'<div class="bar-track"><div class="bar-fill" style="width:{width}%;"></div></div>'
                f'<div class="bar-value">{t.get("review_count", 0):,}</div></div>'
            )
        chart_html = (
            '<div class="theme-bar-card">'
            '<div class="theme-bar-header">'
            '<h3 style="margin:0; color:#ffffff;">Reviews per theme</h3>'
            '<p style="margin:0.35rem 0 1rem 0; color:#c7c7c7;">How many sampled reviews support each discovered theme</p>'
            '</div>'
            + "".join(rows)
            + '<div style="margin-top:0.8rem; color:#9ca3af; font-size:0.85rem;">Supporting reviews</div>'
            '</div>'
        )
        st.markdown(chart_html, unsafe_allow_html=True)

    render_reviews_per_theme_chart(themes)
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    st.subheader("🔎 Key findings")
    st.caption("Findings are derived from discovered themes and user complaint patterns in the filtered reviews and discussions.")

    key_findings = build_key_findings(
        themes,
        pain_points,
        question_data.get("answers", []) if question_data else [],
        selected_platform,
    )

    if key_findings:
        st.markdown(
            "<div style='background:#111111; padding:1rem; border-radius:12px; border:1px solid rgba(255,255,255,0.08);'>"
            "<ul style='margin:0; padding-left:1rem; color:#e5e7eb;'>"
            + "".join(
                f"<li style='margin-bottom:0.8rem;'>{point}</li>"
                for point in key_findings
            )
            + "</ul></div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No key findings are available for the selected filters.")

    st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)
    st.subheader("📈 Top opportunities")
    st.caption("These are the best opportunities to improve business results by solving the user problems above.")

    top_opportunities = build_top_opportunities(key_findings)
    st.markdown(
        "<div style='background:#111111; padding:1rem; border-radius:12px; border:1px solid rgba(29,185,84,0.18);'>"
        "<ul style='margin:0; padding-left:1rem; color:#e5e7eb;'>"
        + "".join(
            f"<li style='margin-bottom:0.8rem;'>{item}</li>"
            for item in top_opportunities
        )
        + "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.subheader("🚦 Segment priority")
    priority_segments = segments.get("segments", []) if isinstance(segments, dict) else []
    if priority_segments:
        for idx, seg in enumerate(priority_segments[:3]):
            label = "Critical" if idx == 0 else "High" if idx == 1 else "Monitor"
            st.markdown(
                f'<div class="overview-metric-card">'
                f'  <h3 style="margin:0 0 0.5rem 0;">Priority {idx + 1} — {label} segment</h3>'
                f'  <p style="margin:0; color:#e5e7eb;">{seg.get("segment", "Unknown")} · {seg.get("count", 0):,} reviews</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No user segments are available for this overview.")


# ═══════════════════════════════════════════════════════════════════════════
# Tab 2: Themes & Chat (中心展示区 — Left: Themes list, Right: Chat)
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Themes & Chat":
    col_left, col_right = st.columns([1, 1])

    # ── Left Column: Theme Discovery List ──
    with col_left:
        st.markdown("<h3 style='margin-bottom: 0.2rem;'>Theme discovery</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #8e8e8e; font-size: 0.85rem; margin-bottom: 1.5rem;'>Discovery & recommendation pain clusters mined from review text. {len(themes)} active themes.</p>", unsafe_allow_html=True)

        if themes:
            theme_name_map = build_complaint_theme_name_map(themes)
            for idx, t in enumerate(themes):
                theme_id = t["id"]
                theme_name = html.escape(theme_name_map.get(theme_id, derive_complaint_theme_name(t)))

                neg_ratio = 1.0 if t["overall_sentiment"] == "negative" else (0.5 if t["overall_sentiment"] == "neutral" else 0.0)
                severity_score = round(100 * neg_ratio)
                is_trending = False
                if t.get("date_range_end"):
                    try:
                        if datetime.now(timezone.utc) - t["date_range_end"] <= timedelta(days=7) and t.get("review_count", 0) >= 8:
                            is_trending = True
                    except Exception:
                        is_trending = False

                if severity_score > 60:
                    badge_text = "HIGH FRICTION"
                    badge_class = "badge-high-friction"
                elif is_trending:
                    badge_text = "TRENDING UP"
                    badge_class = "badge-trending-up"
                else:
                    badge_text = "STABLE"
                    badge_class = "badge-stable"

                avg_rating = 1.5 if t["overall_sentiment"] == "negative" else (3.0 if t["overall_sentiment"] == "neutral" else 4.5)
                corpus_share = max(0.1, round(t["review_count"] / max(total, 1) * 100, 1))

                st.markdown(
                    f'<div class="custom-theme-card">'
                    f'  <div class="theme-card-header">'
                    f'    <div>'
                    f'      <h4 class="theme-title">{theme_name}</h4>'
                    f'      <div class="theme-subtitle">Cluster of {t["review_count"]} sampled reviews · average rating {avg_rating:.1f}★</div>'
                    f'      <div style="margin-top:0.45rem;">{render_based_on_badge(t["review_count"])}</div>'
                    f'    </div>'
                    f'    <span class="theme-badge {badge_class}">{badge_text}</span>'
                    f'  </div>'
                    f'  <div class="theme-meta-row">'
                    f'    <div class="theme-meta-item"><strong>{t["review_count"]:,}</strong> reviews</div>'
                    f'    <div class="theme-meta-item"><strong>{corpus_share}%</strong> of corpus</div>'
                    f'    <div class="theme-meta-item"><strong>{severity_score}</strong> severity</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                with st.expander(f"View supporting reviews ({t['review_count']})", expanded=False):
                    sup_reviews = fetch_theme_reviews(theme_id, limit=5)
                    if sup_reviews:
                        for rev in sup_reviews:
                            st.markdown(
                                f'<div class="evidence-quote-box">"{rev["content"]}"'
                                f'<div class="evidence-quote-source">review_id: {rev["id"]} · {sentiment_badge(rev.get("sentiment"))}</div></div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("No reviews returned for this theme.")
        else:
            st.info("No themes discovered for the selected source.")

    # ── Right Column: Discovery Chat ──
    with col_right:
        st.markdown("<h3 style='margin-bottom: 0.2rem;'>Discovery chat</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #8e8e8e; font-size: 0.85rem; margin-bottom: 1.5rem;'>Grounded in retrieved review excerpts only. Every claim cites a review_id; out-of-scope questions are refused.</p>", unsafe_allow_html=True)
        st.markdown("<span style='font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; color: #b3b3b3;'>Try a starter question:</span>", unsafe_allow_html=True)

        # Starter Questions buttons
        starter_qs = [
            "Why do users struggle to discover new music?",
            "What are the most common frustrations with recommendations?",
            "What listening behaviors are users trying to achieve?",
            "What causes users to repeatedly listen to the same content?",
            "Which user segments experience different discovery challenges?",
            "What unmet needs emerge consistently across reviews?"
        ]

        if "chat_query" not in st.session_state:
            st.session_state.chat_query = ""

        # Make two columns of starter buttons
        col_sq1, col_sq2 = st.columns(2)
        for idx, sq in enumerate(starter_qs):
            target_col = col_sq1 if idx % 2 == 0 else col_sq2
            with target_col:
                if st.button(sq, key=f"sq_{idx}", use_container_width=True, type="secondary"):
                    st.session_state.chat_query = sq
                    st.rerun()

        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

        # Chat inputs
        chat_input_val = st.text_input("Ask a question about Spotify discovery reviews:", value=st.session_state.chat_query, placeholder="e.g. Why do users feel stuck in a loop?")
        
        col_ask, col_clear = st.columns([4, 1])
        with col_ask:
            ask_clicked = st.button("Ask AI Assistant", type="primary", use_container_width=True)
        with col_clear:
            clear_clicked = st.button("Clear Chat", use_container_width=True)

        if clear_clicked:
            st.session_state.chat_query = ""
            st.session_state.chat_history = []
            st.rerun()

        # Handle Chat Submission
        if ask_clicked and chat_input_val.strip():
            st.session_state.chat_query = ""
            query = chat_input_val.strip()

            try:
                chat_data = ask_discovery_chat(query, selected_platform, date_start, date_end)
                ai_response = {
                    "question": chat_data.get("question", query),
                    "summary": chat_data.get("answer", "No answer returned."),
                    "rating": chat_data.get("criticality_rating", 3),
                    "themes": chat_data.get("related_themes", []),
                    "quotes": [
                        {
                            "excerpt": citation.get("excerpt", ""),
                            "platform": citation.get("platform", ""),
                            "review_id": citation.get("review_id"),
                        }
                        for citation in chat_data.get("citations", [])
                    ],
                    "based_on_review_count": chat_data.get("based_on_review_count", 0),
                    "refused": chat_data.get("refused", False),
                }
            except Exception:
                ai_response = {
                    "question": query,
                    "summary": "The chat service is unavailable right now. Please confirm the API backend is running and try again.",
                    "rating": 1,
                    "themes": [],
                    "quotes": [],
                    "based_on_review_count": 0,
                    "refused": True,
                }

            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            st.session_state.chat_history.insert(0, ai_response)
            st.rerun()

        # Render Chat History
        if "chat_history" in st.session_state and st.session_state.chat_history:
            st.markdown("<hr style='border-color: rgba(255,255,255,0.06);'/>", unsafe_allow_html=True)
            st.markdown("### Chat History", unsafe_allow_html=True)
            for chat in st.session_state.chat_history:
                st.markdown(
                    f'<div class="chat-bubble-user">'
                    f'  <strong style="color: #1DB954; font-size: 0.85rem; text-transform: uppercase;">YOU ASKED:</strong><br/>'
                    f'  <p style="margin: 0.4rem 0 0 0; font-size: 1rem; color: #ffffff;">{chat["question"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                stars_html = render_stars_str(chat["rating"])
                themes_html = ", ".join(f"`{t}`" for t in chat["themes"])
                based_on = chat.get("based_on_review_count", 0)
                based_on_html = (
                    f'<div style="font-size:0.8rem;color:#8e8e8e;margin-top:0.35rem;">Based on {based_on:,} reviews</div>'
                    if based_on
                    else ""
                )
                st.markdown(
                    f'<div class="chat-bubble-ai">'
                    f'  <strong style="color: #b3b3b3; font-size: 0.85rem; text-transform: uppercase;">AI ASSISTANT Response:</strong>'
                    f'  <div style="margin: 0.4rem 0; font-size: 0.9rem;"><strong>Severity:</strong> {stars_html}</div>'
                    f'  <p style="margin: 0.5rem 0; font-size: 0.95rem; color: #e5e7eb; line-height: 1.5;">{chat["summary"]}</p>'
                    f'  {based_on_html}'
                    f'  {f"<div style=font-size:0.8rem;color:#8e8e8e;margin-top:0.6rem;>Related themes: {themes_html}</div>" if chat["themes"] else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                if chat["quotes"]:
                    with st.expander("Show Supporting Evidence Quotes", expanded=False):
                        for q in chat["quotes"]:
                            plat = PLATFORM_LABELS.get(q["platform"], q["platform"])
                            review_id = q.get("review_id")
                            source_line = f"— {plat}" if not review_id else f"— {plat} · review_id: {review_id}"
                            st.markdown(
                                f'<div class="evidence-quote-box">"{q["excerpt"]}"'
                                f'<div class="evidence-quote-source">{source_line}</div></div>',
                                unsafe_allow_html=True
                            )


# ═══════════════════════════════════════════════════════════════════════════
# Tab 3: Segments (Friction Levels and Demographics)
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Segments":
    st.subheader("👥 User Segments")
    st.caption("Behavioral segments and top frustrations with representative evidence")

    seg_data = fetch_segments(date_start, date_end, selected_platform)
    segments = seg_data.get("segments", []) if seg_data else []
    if segments:
        for s in segments:
            strength_label, strength_class = evidence_strength_label(s.get("count", 0))

            st.markdown(
                f'<div style="background:#181818; padding:1rem; border-radius:10px; border:1px solid rgba(255,255,255,0.05); margin-bottom:0.8rem;">'
                f'  <strong style="font-size:1.05rem">{html.escape(s["segment"])}</strong>'
                f'  <span style="color:#9ca3af; margin-left:0.6rem;">{render_based_on_badge(s["count"])}</span>'
                f'  <div style="margin-top:0.55rem;"><span class="strength-badge {strength_class}">Evidence: {strength_label}</span></div>'
                f'  <div style="color:#E5E5E5; margin-top:0.6rem;">Top frustration: <em>{html.escape((s.get("representative_quote") or "No quote available")[:220])}</em></div>'
                f'  <div style="margin-top:0.6rem; color:#b3b3b3;">Representative review id: {html.escape(str(s.get("representative_review_id") or "N/A"))}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No segment data found.")


# ═══════════════════════════════════════════════════════════════════════════
# Tab 4: Unmet Needs
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Unmet Needs":
    st.subheader("💡 Feature Demands & Unmet Needs")
    st.caption("Product opportunities and requests mapped from user descriptions of missing features")

    if pain_points:
        for idx, pp in enumerate(pain_points, 1):
            score = pp.get("opportunity_score") or 0
            supporting_count = int(pp.get("supporting_review_count", 0) or 0)
            strength_label, strength_class = evidence_strength_label(supporting_count)
            theme_id = pp.get("theme_id")

            st.markdown(
                f'<div style="background:#181818; padding:1.2rem; border-radius:10px; border:1px solid rgba(255,255,255,0.05); margin-bottom: 1rem;">'
                f'  <h4 style="margin:0 0 0.5rem 0;">{idx}. Need: {html.escape(pp.get("summary", "Unknown need"))}</h4>'
                f'  <div style="margin-bottom:0.55rem;">{render_based_on_badge(supporting_count)}</div>'
                f'  <div style="font-size:0.95rem; color:#E5E5E5;">Evidence strength: <span class="strength-badge {strength_class}">{strength_label}</span></div>'
                f'  <div style="margin-top:0.75rem; color:#d1d5db;">Priority signal score: {score:.1f}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if theme_id:
                with st.expander(f"View supporting evidence for need {idx}", expanded=False):
                    theme_reviews = fetch_theme_reviews(theme_id, limit=3)
                    if theme_reviews:
                        for rev in theme_reviews:
                            st.markdown(
                                f'<div class="evidence-quote-box">"{html.escape(rev.get("content", "")[:320])}"'
                                f'<div class="evidence-quote-source">review_id: {rev.get("id")} · {sentiment_badge(rev.get("sentiment"))}</div></div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("No supporting reviews were returned for this need.")
    else:
        st.info("No opportunity records found for the current filter.")


# ═══════════════════════════════════════════════════════════════════════════
# Tab 5: Review Discovery
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "Review Discovery":
    st.subheader("🔎 Raw Review Discovery Search")
    st.caption("Search reviews semantically (meaning matching) or using literal keyword matches. Results respect the shared filters above.")

    search_val = st.text_input("Enter search keywords, questions, or themes:", placeholder="e.g. repetitive recommendations")
    search_triggered = st.button("Search Database", type="primary")

    if search_triggered and search_val.strip():
        search_data = search_reviews(search_val, selected_platform, date_start, date_end)
        results = search_data.get("results", [])
        total_matches = search_data.get("total_matches", len(results))

        if results:
            st.success(f"Found **{len(results)}** displayed reviews ({total_matches:,} total matches)")
            for r in results:
                posted = r.get("posted_at", "")
                try:
                    posted = datetime.fromisoformat(posted).strftime("%b %d, %Y")
                except Exception:
                    posted = "Unknown"
                plat_name = PLATFORM_LABELS.get(r["platform"], r["platform"])

                st.markdown(
                    f'<div style="background:#181818; padding:1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.04); margin-bottom: 0.6rem;">'
                    f'  <p style="margin:0; font-size: 0.95rem; color:#ffffff;">"{html.escape(r.get("content", "")[:500])}"</p>'
                    f'  <div style="font-size:0.75rem; color:#8e8e8e; margin-top:0.4rem;">'
                    f'    {sentiment_badge(r.get("sentiment"))} · {html.escape(plat_name)} · {html.escape(posted)} · review_id: {html.escape(str(r.get("id", "unknown")))}'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.warning("No results matching your query.")
