import streamlit as st
import requests
import pandas as pd
from PIL import Image
import os
import importlib.util
import sys

FAST_API_URL = "http://localhost:8000"

# Dynamically add project root (InvestorIntel.Ai/) to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ✅ Now do the imports
# from backend.database import db_utils

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

def fetch_report(column_name, startup_id):
    resp = requests.post(
        f"{FAST_API_URL}/get-startup-column",
        json={"column_name": column_name, "startup_id": startup_id}
    )
    if resp.status_code == 200:
        return resp.json().get("value")
    else:
        # you could st.error() here or return None
        return None

def dashboard_header(first_name):
    # Set padding to 0 for top alignment
    st.markdown("""
            <style>
            /* Keep small top padding to avoid image clipping */
            .block-container {
                padding-top: 0.5rem !important;
            }
            .welcome-text {
                text-align: left;
                margin-top: 30px;
                font-size: 22px;
            }
            /* Prevent image cropping */
            .stImage > img {
                margin-top: 0 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Columns with precise proportions
    header_col1, header_col2, header_col3 = st.columns([1.3, 4.7, 1])

    with header_col1:
        logo_path = os.path.join(PROJECT_ROOT, "frontend", "assets", "InvestorIntel_Logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=150)
        else:
            st.warning("⚠️ Logo image not found.")

    with header_col2:
        st.markdown(
            f"<h3 style='text-align:left; margin-top: 30px;'>👋 Welcome, {first_name}!</h3>",
            unsafe_allow_html=True
        )

    with header_col3:
        st.write("")  # vertical alignment spacer
        st.write("")
        if st.button("🚪 Logout"):
            st.session_state.page = "home"
            st.session_state.is_logged_in = False
            st.rerun()

    # 🧱 Horizontal divider comes immediately after header
    st.markdown("<hr style='border: 1px solid #ccc; margin-top: 0;'>", unsafe_allow_html=True)

def dashboard_sidebar(sidebar_col, investor_id):
    with sidebar_col:
        with st.container():
            st.markdown("<div class='sidebar-container'>", unsafe_allow_html=True)

            # 📌 Status Filters
            st.markdown("### 📌 Select Startup")
            status_options = {
                "New":      "Not Viewed",
                "Reviewed": "Decision Pending",
                "Funded":   "Funded",
                "Rejected": "Rejected"
            }
            selected_status_key = st.radio("**Stage:**", list(status_options.keys()))
            selected_status = status_options[selected_status_key]

            # 📄 Startup List via FastAPI
            resp = requests.post(
                f"{FAST_API_URL}/fetch-startups-by-status",
                json={"investor_id": investor_id, "status": selected_status}
            )
            data = resp.json()
            startup_list = data.get("startups", [])

            if not startup_list:
                st.info("No startups found in this category.")
                st.session_state.selected_startup_id = None
            else:
                # Extract just the names for the Selectbox
                startup_names = [s["startup_name"] for s in startup_list]
                selected_name  = st.selectbox("**📄 Startups:**", startup_names)

                # Find the matching ID
                selected_id = next(
                    s["startup_id"]
                    for s in startup_list
                    if s["startup_name"] == selected_name
                )
                st.session_state.selected_startup_id = selected_id

            st.markdown("</div>", unsafe_allow_html=True)


def dashboard_main(main_col):
    with main_col:
        startup_id = st.session_state.get("selected_startup_id")
        if not startup_id:
            st.info("Select a startup from the left panel to view details.")
            return

        # Load startup data once
        # startup_data = db_utils.get_startup_info_by_id(st.session_state.selected_startup_id)
        resp = requests.post(
            f"{FAST_API_URL}/fetch-startup-info",
            json={"startup_id": st.session_state.selected_startup_id}
        )
        data = resp.json()
        if data.get("status") == "success":
            startup_data = data["startup"]
            # e.g. display details:
            # st.write(startup_data)
        else:
            st.error(data.get("detail", "Unknown error"))

        # Create Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📄 Summary", "📊 Competitor Analysis", "📈 Market Analysis", "📰 News Trends"])

        # ---------- 🟢 Summary Tab ----------
        with tab1:
            st.markdown("## 🚀 Startup Details")
            st.markdown(f"**Name:** {startup_data['STARTUP_NAME']}")
            st.markdown(f"**Industry:** {startup_data['INDUSTRY']}")
            st.markdown(f"**Email:** {startup_data['EMAIL_ADDRESS']}")
            st.markdown(f"**Website:** [Visit]({startup_data['WEBSITE_URL']})")
            st.markdown(f"**Valuation Ask:** ${startup_data['VALUATION_ASK']:,.2f}")

            if startup_data["PITCH_DECK_LINK"]:
                st.markdown(f"[📄 View Pitch Deck]({startup_data['PITCH_DECK_LINK']})")

            if startup_data.get("ANALYTICS_REPORT"):
                st.download_button("📊 Download Analytics Report", data=startup_data["ANALYTICS_REPORT"], file_name="analytics_report.txt")

            summary_text = fetch_report("summary_report", startup_id)
            st.info(summary_text)


        # ---------- 🟡 Competitor Analysis Tab ----------
        with tab2:
            st.markdown("### 🧩 Competitor Analysis")
            st.info("Competitor analysis content goes here...")
               # or "analytics_report" if that’s your real column


        # ---------- 🔵 Market Analysis Tab ----------
        with tab3:
            st.markdown("### 🌐 Market Analysis")
            st.info("Market trends, segmentation, and other analysis will be shown here...")
            analytics_text = fetch_report("analytics_report", startup_id) 
            st.info(analytics_text)

        # ---------- 🔴 News Trends Tab ----------
        with tab4:
            st.markdown("### 🗞️ News Trends")
            st.info("Latest news and trends related to this startup will be displayed here...")
            news_text = fetch_report("news_report", startup_id)
            st.info(news_text)


def render():
    if not st.session_state.get("is_logged_in"):
        st.warning("You must log in first.")
        st.session_state.page = "home"
        st.rerun()

    investor_username = st.session_state.username
    # investor_info = db_utils.get_investor_by_username(investor_username)
    resp = requests.post(
        f"{FAST_API_URL}/fetch-investor-by-username",
        json={"username": st.session_state.username}
    )
    data = resp.json()
    if data.get("status") == "success":
        investor_info = data["investor"]
        # e.g. display fields:
        #st.write(investor_info)
    else:
        st.error(data.get("detail", "Unknown error"))

    investor_id = investor_info["INVESTOR_ID"]
    first_name = investor_info["FIRST_NAME"]

    # ←——— INSERT THIS ENTIRE BLOCK right here, before you call dashboard_header()
    st.markdown("""
        <style>
    .header {
        position: sticky;
        top: 0;
        z-index: 100;
        background-color: white;
    }

    .content-scroll {
        /* fill the viewport below your 70px header */
        height: calc(1vh - 70px);
        margin-top: 0;      /* no extra gap */
        padding-top: 0;     /* ditto */
        overflow-y: auto;
    }

    .sidebar-container {
        border-right: 1px solid #ccc;
        padding-right: 15px;
    }

    .block-container {
        padding-top: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # -------- 🧢 HEADER (Logo + Welcome + Logout) --------
    # ←——— WRAP your header call inside this div
    st.markdown('<div class="header">', unsafe_allow_html=True)
    dashboard_header(first_name)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------- 🧭 MAIN LAYOUT (Sidebar + Main) --------
    # 👉 Wrap sidebar in scrollable styled container with right border
    st.markdown("""
        <style>
            .sidebar-container {
                border-right: 5px solid #ccc;
                padding-right: 15px;
                max-height: 75vh;
                overflow-y: auto;
            }
        </style>
    """, unsafe_allow_html=True)

    # ←——— NOW start the scrollable wrapper just before your columns
    st.markdown('<div class="home-scroll">', unsafe_allow_html=True)

    sidebar_col, main_col = st.columns([1.3, 5.7])
    dashboard_sidebar(sidebar_col, investor_id)
    dashboard_main(main_col)

    # ←——— CLOSE the scrollable wrapper right after your main content
    st.markdown('</div>', unsafe_allow_html=True)