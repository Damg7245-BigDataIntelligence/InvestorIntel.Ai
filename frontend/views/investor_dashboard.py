import streamlit as st
import pandas as pd
from PIL import Image
import os
import importlib.util
import sys

# Dynamically add project root (InvestorIntel.Ai/) to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ✅ Now do the imports
from backend.database import db_utils


def render():
    if not st.session_state.get("is_logged_in"):
        st.warning("You must log in first.")
        st.session_state.page = "home"
        st.experimental_rerun()

    investor_username = st.session_state.username
    investor_info = db_utils.get_investor_by_username(investor_username)
    investor_id = investor_info["investor_id"]
    first_name = investor_info["first_name"]

    # --------------------- 🔝 Top Header ---------------------
    with st.container():
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            logo_path = os.path.join("assets", "InvestorIntel_Logo.png")
            logo = Image.open(logo_path)
            if st.button("🏠"):
                st.session_state.page = "investor_dashboard"
                st.experimental_rerun()
            st.image(logo, width=80)

        with col2:
            st.markdown(f"<h3 style='text-align:center;'>👋 Welcome, {first_name}!</h3>", unsafe_allow_html=True)

        with col3:
            if st.button("🚪 Logout"):
                st.session_state.page = "home"
                st.session_state.is_logged_in = False
                st.experimental_rerun()

    st.markdown("---")

    # ------------------ 📁 NavBar 1: Status ------------------
    st.subheader("🔍 Filter Startups by Status")
    status_options = {
        "New": "Not Viewed",
        "Reviewed": "Decision Pending",
        "Funded": "Funded",
        "Rejected": "Rejected"
    }
    selected_status_key = st.radio("Select Startup Stage:", list(status_options.keys()), horizontal=True)
    selected_status = status_options[selected_status_key]

    # ------------------ 📌 NavBar 2: Startup List ------------------
    startup_list = db_utils.get_startups_by_status(investor_id, selected_status)
    if startup_list.empty:
        st.info("No startups found in this category.")
        return

    selected_startup_name = st.selectbox("Choose a startup to view details:", startup_list["startup_name"].tolist())
    selected_startup_id = startup_list[startup_list["startup_name"] == selected_startup_name]["startup_id"].values[0]

    # ------------------ 📊 Main Body: Startup Info ------------------
    startup_data = db_utils.get_startup_info_by_id(selected_startup_id)

    st.markdown("### 🚀 Startup Details")
    st.markdown(f"**Name:** {startup_data['startup_name']}")
    st.markdown(f"**Industry:** {startup_data['industry']}")
    st.markdown(f"**Founder:** {startup_data['founder_name']}")
    st.markdown(f"**Email:** {startup_data['email_address']}")
    st.markdown(f"**Website:** [Visit]({startup_data['website_url']})")
    st.markdown(f"**LinkedIn:** [Profile]({startup_data['linkedin_url']})")
    st.markdown(f"**Valuation Ask:** ${startup_data['valuation_ask']:,.2f}")
    st.markdown(f"**Short Description:** {startup_data['short_description']}")

    if startup_data["pitch_deck_link"]:
        st.markdown(f"[📄 View Pitch Deck]({startup_data['pitch_deck_link']})")

    if startup_data.get("analytics_report"):
        st.download_button("📊 Download Analytics Report", data=startup_data["analytics_report"], file_name="analytics_report.txt")

