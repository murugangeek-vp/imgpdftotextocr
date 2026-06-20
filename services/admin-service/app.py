"""
OCR Platform — Admin Dashboard (Streamlit)
Real-time monitoring, tier config management, and job oversight.
"""
import asyncio
import os
import time
from datetime import datetime, timedelta

import httpx
import streamlit as st

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR Platform Admin",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Style ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .stMetric { background: #1e1e2e; border-radius: 8px; padding: 1rem; }
    .stButton>button { background: #7c3aed; color: white; border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Config ────────────────────────────────────────────────────────────────────
QUOTA_SERVICE = os.getenv("QUOTA_SERVICE_URL", "http://quota-service:8003")
RESULT_SERVICE = os.getenv("RESULT_SERVICE_URL", "http://result-service:8004")
INGESTION_SERVICE = os.getenv("INGESTION_SERVICE_URL", "http://ingestion-service:8002")

TIER_OPTIONS = ["free", "basic", "pro"]


# ── Helper Functions ──────────────────────────────────────────────────────────
def get_tier_configs():
    try:
        resp = httpx.get(f"{QUOTA_SERVICE}/api/v1/tiers", timeout=3.0)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def update_tier_config(tier: str, limits: dict):
    try:
        resp = httpx.put(
            f"{QUOTA_SERVICE}/api/v1/tiers/{tier}",
            json={"limits": limits},
            timeout=5.0,
        )
        return resp.status_code == 200, resp.text
    except Exception as e:
        return False, str(e)


def service_health(url: str, name: str) -> bool:
    try:
        resp = httpx.get(f"{url}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🔬 OCR Platform")
st.sidebar.markdown("**Admin Dashboard**")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Overview", "⚙️ Tier Config", "📋 Jobs Monitor", "🔑 API Keys"],
)

# ── Page: Overview ────────────────────────────────────────────────────────────
if page == "📊 Overview":
    st.title("📊 Platform Overview")
    st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")

    col1, col2, col3, col4 = st.columns(4)

    services = [
        ("Quota Service", QUOTA_SERVICE),
        ("Ingestion Service", INGESTION_SERVICE),
        ("Result Service", RESULT_SERVICE),
    ]

    healthy = sum(1 for name, url in services if service_health(url, name))

    with col1:
        st.metric("🟢 Services Healthy", f"{healthy}/{len(services)}")
    with col2:
        st.metric("📄 Tier Configs", "3 (free/basic/pro)")
    with col3:
        st.metric("🤖 OCR Engine", "Triton (CPU Mock)")
    with col4:
        st.metric("💬 LLM Router", "auto (GPT-4o / Ollama)")

    st.divider()
    st.subheader("Service Health Status")
    for name, url in services:
        healthy = service_health(url, name)
        status = "✅ Healthy" if healthy else "❌ Unreachable"
        st.markdown(f"**{name}**: {status} — `{url}`")

    if st.button("🔄 Refresh"):
        st.rerun()

# ── Page: Tier Config ─────────────────────────────────────────────────────────
elif page == "⚙️ Tier Config":
    st.title("⚙️ Dynamic Tier Configuration")
    st.info(
        "Changes are **hot-reloaded** within 60 seconds. "
        "No server restart or redeployment required."
    )

    configs = get_tier_configs()

    if not configs:
        st.warning("Could not fetch tier configs from Quota Service. Is it running?")
        st.json(
            {
                "free": {"pages_per_session": 5, "pages_per_day": 5},
                "basic": {"pages_per_session": 20, "pages_per_day": 100},
                "pro": {"pages_per_session": -1, "pages_per_day": -1},
            }
        )
    else:
        for cfg in configs:
            tier = cfg["tier"]
            limits = cfg.get("limits", {})
            with st.expander(f"🏷️ {tier.upper()} Tier", expanded=(tier == "free")):
                st.json(limits)

    st.divider()
    st.subheader("✏️ Update Tier Limit")
    tier_select = st.selectbox("Select Tier", TIER_OPTIONS)

    col1, col2 = st.columns(2)
    with col1:
        pages_session = st.number_input("Pages per session (-1 = unlimited)", value=5, min_value=-1)
        pages_day = st.number_input("Pages per day (-1 = unlimited)", value=5, min_value=-1)
        pages_week = st.number_input("Pages per week", value=20, min_value=-1)
        concurrent_sessions = st.number_input("Concurrent sessions", value=5, min_value=1)
    with col2:
        pages_month = st.number_input("Pages per month", value=50, min_value=-1)
        max_file_mb = st.number_input("Max file size (MB)", value=10, min_value=1)
        max_pages_pdf = st.number_input("Max pages per PDF", value=5, min_value=1, max_value=100)
        result_retention_hours = st.number_input("Result retention hours", value=24, min_value=1)

    if st.button("💾 Save Changes"):
        ok, msg = update_tier_config(
            tier_select,
            {
                "pages_per_session": pages_session,
                "pages_per_day": pages_day,
                "pages_per_week": pages_week,
                "pages_per_month": pages_month,
                "max_file_size_mb": max_file_mb,
                "max_pages_per_pdf": max_pages_pdf,
                "concurrent_sessions": concurrent_sessions,
                "result_retention_hours": result_retention_hours,
            },
        )
        if ok:
            st.success(f"✅ {tier_select} tier updated! Hot-reload in ~60s.")
        else:
            st.error(f"❌ Update failed: {msg}")

# ── Page: Jobs Monitor ────────────────────────────────────────────────────────
elif page == "📋 Jobs Monitor":
    st.title("📋 Jobs Monitor")

    user_id_filter = st.text_input("Filter by User ID", placeholder="e.g. dev-user-id")

    if user_id_filter:
        try:
            resp = httpx.get(
                f"{RESULT_SERVICE}/api/v1/results/user/{user_id_filter}", timeout=5.0
            )
            if resp.status_code == 200:
                jobs = resp.json()
                if jobs:
                    st.success(f"Found {len(jobs)} jobs")
                    for job in jobs[:20]:
                        status_emoji = {
                            "completed": "✅",
                            "queued": "⏳",
                            "processing": "🔄",
                            "failed": "❌",
                        }.get(job.get("status"), "❓")
                        with st.expander(
                            f"{status_emoji} {job.get('file_name', 'unknown')} — {job.get('status')} — {job.get('job_id', '')[:8]}..."
                        ):
                            st.json(job)
                else:
                    st.info("No jobs found for this user.")
            else:
                st.error(f"Error fetching jobs: {resp.status_code}")
        except Exception as e:
            st.error(f"Could not connect to Result Service: {e}")

# ── Page: API Keys ────────────────────────────────────────────────────────────
elif page == "🔑 API Keys":
    st.title("🔑 API Keys")
    st.info(
        "**Development API Key:** `dev-api-key-12345` (Pro tier, always available in local mode)"
    )
    st.markdown("""
    ### How to use the API:
    ```bash
    # Generate a JWT token for local testing
    curl -X POST http://localhost:8001/api/v1/auth/token \\
      -H "Content-Type: application/json" \\
      -d '{"user_id": "my-user", "email": "me@example.com", "tier": "pro"}'

    # Upload a file
    curl -X POST http://localhost:8080/api/v1/upload \\
      -F "file=@document.pdf" \\
      -F "user_id=my-user" \\
      -F "session_id=session-001" \\
      -F "tier=pro"

    # Subscribe to real-time job updates
    curl -N http://localhost:8080/api/v1/jobs/{job_id}/stream
    ```
    """)
