import streamlit as st
import requests
import pandas as pd
from PIL import Image
import os
import importlib.util
import sys
import plotly.graph_objects as go
import json
import re

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

# Function to convert formatted text to plain text with proper bullet formatting
def convert_to_plain_text(text):
    # Remove the initial information line if present
    text = re.sub(r'^Here\'s the (CEO )?information.*?:', '', text)
    text = re.sub(r'^Based on the provided search results:?', '', text)
    text = re.sub(r'^Here are the.*?:', '', text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Replace HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    
    # Replace Markdown emphasis and bold with plain text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold **text**
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove italic *text*
    
    # Remove result references (e.g., "(Result #2)")
    text = re.sub(r'\s*\(Result #\d+\)', '', text)
    text = re.sub(r'\s*\(Source \d+\)', '', text)
    
    # Split into lines for processing
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            lines.append('')
            continue
            
        # Process bullet points on same line
        if '• ' in line and not line.startswith('• '):
            parts = re.split(r'(• )', line)
            result = []
            for i in range(len(parts)):
                if parts[i] == '• ' and i > 0 and parts[i-1] != '':
                    # This is a bullet point that needs to start on a new line
                    result.append('\n• ')
                else:
                    result.append(parts[i])
            lines.append(''.join(result))
        else:
            # Handle other bullets format
            if line.startswith('* ') or line.startswith('- '):
                line = '• ' + line[2:]
            lines.append(line)
    
    # Join lines back
    text = '\n'.join(lines)
    
    # Make sure each bullet point starts on a new line
    text = re.sub(r'([^\n])• ', r'\1\n• ', text)
    
    # Fix spacing after bullet points
    text = re.sub(r'•\s*', '• ', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text

def fetch_report(column_name, startup_id):
    resp = requests.post(
        f"{FAST_API_URL}/get-startup-column",
        json={"column_name": column_name, "startup_id": startup_id}
    )
    if resp.status_code == 200:
        value = resp.json().get("value")
        # For visualization data, we need to ensure it's valid JSON
        if column_name == "competitor_visualizations" and value:
            try:
                # Try to parse JSON if it's not already parsed
                if isinstance(value, str):
                    return json.loads(value)
                return value
            except json.JSONDecodeError:
                print(f"Failed to parse visualization JSON: {value}")
                return None
        return value
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
                selected_name = st.selectbox("**📄 Startups:**", startup_names)
                
                # When a startup is selected, disable chat mode
                if selected_name:
                    st.session_state.show_chat = False

                # Find the matching ID
                selected_id = next(
                    s["startup_id"]
                    for s in startup_list
                    if s["startup_name"] == selected_name
                )
                st.session_state.selected_startup_id = selected_id
            
            # Add divider
            st.markdown("---")
            
            # Add Q&A Bot Button
            st.markdown("### 💬 AI Assistant")
            if st.button("Ask Anything"):
                # Enable chat mode and clear startup selection
                st.session_state.show_chat = True
                st.session_state.selected_startup_id = None
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


def dashboard_main(main_col):
    with main_col:
        # Handle chat display if enabled - mutually exclusive with startup view
        if st.session_state.get("show_chat", False):
            st.markdown("## 💬 InvestorIntel AI Assistant")
            st.markdown("Ask me any questions about startups, market trends, or investment strategies.")
            
            # Initialize chat history if not exists
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            
            # Create a container for chat history
            chat_container = st.container()
            
            # Display chat history
            with chat_container:
                for i, message in enumerate(st.session_state.chat_history):
                    if message["role"] == "user":
                        # For user messages, use a styled div
                        st.markdown(f"""
                        <div class="question-box">
                        {message["content"]}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # For assistant messages, use a styled div with properly formatted text
                        plain_text = convert_to_plain_text(message["content"])
                        st.markdown(f"""
                        <div class="answer-box">
                        {plain_text}
                        </div>
                        """, unsafe_allow_html=True)
            
            # Create a container for the input area
            input_container = st.container()
            
            # Add a form with a single-line input field
            with input_container:
                with st.form(key="dashboard_chat_form", clear_on_submit=True):
                    # Small fixed-height input field
                    user_input = st.text_input("", key="dashboard_chat_input", placeholder="Type your question here...")
                    
                    # Add submit button at the bottom
                    submit_button = st.form_submit_button("Send")
                    
                    if submit_button and user_input:
                        # Get the user's query
                        query = user_input
                        
                        # Add user message to chat history
                        st.session_state.chat_history.append({"role": "user", "content": query})
                        
                        # Send query to backend
                        with st.spinner('Searching database...'):
                            try:
                                response = requests.post(
                                    f"{FAST_API_URL}/chat",
                                    json={"query": query}
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    ai_response = result.get("response", "Sorry, I couldn't find an answer to your question.")
                                    
                                    # Add assistant message to chat history
                                    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
                                else:
                                    error_msg = f"Error: {response.status_code} - {response.text}"
                                    
                                    # Add error message to chat history
                                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                                    
                            except Exception as e:
                                error_msg = f"An error occurred: {str(e)}"
                                
                                # Add error message to chat history
                                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                        
                        # Force a rerun to update the chat history display
                        st.rerun()
            
            # Button to clear chat and return to startup view
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Clear Chat"):
                    st.session_state.chat_history = []
                    st.rerun()
            with col2:
                if st.button("Return to Startups"):
                    st.session_state.show_chat = False
                    st.rerun()
            
            # We return here to avoid showing startup content
            return
        
        # If we're not in chat mode, display startup information
        startup_id = st.session_state.get("selected_startup_id")
        if not startup_id:
            st.info("Select a startup from the left panel to view details.")
            return

        # Load startup data once
        resp = requests.post(
            f"{FAST_API_URL}/fetch-startup-info",
            json={"startup_id": st.session_state.selected_startup_id}
        )
        data = resp.json()
        if data.get("status") == "success":
            startup_data = data["startup"]
        else:
            st.error(data.get("detail", "Unknown error"))
            return

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
            if summary_text:
                st.markdown("### Executive Summary")
                st.info(summary_text)
            else:
                st.info("No summary available for this startup.")

        # ---------- 🟡 Competitor Analysis Tab ----------
        with tab2:
            st.markdown("### 🧩 Competitor Analysis")
            
            visualization_data = fetch_report("competitor_visualizations", startup_id)
            
            if visualization_data:
                try:
                    # Parse the JSON data
                    viz_data = visualization_data
                    if isinstance(viz_data, str):
                        viz_data = json.loads(viz_data)
                    
                    # Create columns for visualization charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if "revenue_chart" in viz_data:
                            st.subheader("Revenue Comparison")
                            revenue_fig = go.Figure(viz_data["revenue_chart"])
                            st.plotly_chart(revenue_fig, use_container_width=True)
                    
                    with col2:
                        if "growth_chart" in viz_data:
                            st.subheader("Growth Metrics")
                            growth_fig = go.Figure(viz_data["growth_chart"])
                            st.plotly_chart(growth_fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error displaying visualizations: {e}")
            else:
                st.info("No competitor analysis data available for this startup.")

        # ---------- 🔵 Market Analysis Tab ----------
        with tab3:
            st.markdown("### 🌐 Market Analysis")
            
            # Display the analytics report
            analytics_text = fetch_report("analytics_report", startup_id) 
            if analytics_text:
                st.markdown("### Market Insights")
                st.info(analytics_text)
            
                # Also display the visualizations in this tab
                visualization_data = fetch_report("competitor_visualizations", startup_id)
                
                if visualization_data:
                    try:
                        # Parse the JSON data
                        viz_data = visualization_data
                        if isinstance(viz_data, str):
                            viz_data = json.loads(viz_data)
                        
                        st.markdown("### Market Position")
                        # Create columns for visualization charts
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if "revenue_chart" in viz_data:
                                st.subheader("Revenue Comparison")
                                revenue_fig = go.Figure(viz_data["revenue_chart"])
                                st.plotly_chart(revenue_fig, use_container_width=True)
                        
                        with col2:
                            if "growth_chart" in viz_data:
                                st.subheader("Growth Metrics")
                                growth_fig = go.Figure(viz_data["growth_chart"])
                                st.plotly_chart(growth_fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error displaying visualizations: {e}")
            else:
                st.info("No market analysis data available for this startup.")

        # ---------- 🔴 News Trends Tab ----------
        with tab4:
            st.markdown("### 🗞️ News Trends")
            news_text = fetch_report("news_report", startup_id)
            if news_text:
                # Parse the news text - assuming format like "Title: URL"
                news_items = news_text.strip().split('\n')
                
                # Display each news item with better formatting
                for item in news_items:
                    if ':' in item:
                        parts = item.split(':', 1)
                        title = parts[0].strip()
                        url = parts[1].strip()
                        st.markdown(f"#### {title}")
                        st.markdown(f"[Read more]({url})")
                        st.markdown("---")
                    else:
                        st.markdown(f"- {item}")
            else:
                st.info("No news data available for this startup.")


def render():
    # Add custom styling for the dashboard and chat components
    st.markdown("""
    <style>
    .main-header {
        font-size: 42px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 10px;
    }
    
    .stButton>button {
        width: 100%;
        background-color: #1E3A8A;
        color: white;
    }
    
    .question-box {
        background-color: #E3F2FD;
        border-left: 4px solid #1E88E5;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    
    .answer-box {
        background-color: #F5F7FF;
        border-left: 4px solid #1E3A8A;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    
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
    
    .sidebar-container {
        border-right: 5px solid #ccc;
        padding-right: 15px;
        max-height: 75vh;
        overflow-y: auto;
    }
    </style>
    """, unsafe_allow_html=True)

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
        return

    investor_id = investor_info["INVESTOR_ID"]
    first_name = investor_info["FIRST_NAME"]

    # -------- 🧢 HEADER (Logo + Welcome + Logout) --------
    st.markdown('<div class="header">', unsafe_allow_html=True)
    dashboard_header(first_name)
    st.markdown('</div>', unsafe_allow_html=True)

    # -------- 🧭 MAIN LAYOUT (Sidebar + Main) --------
    st.markdown('<div class="home-scroll">', unsafe_allow_html=True)

    sidebar_col, main_col = st.columns([1.3, 5.7])
    dashboard_sidebar(sidebar_col, investor_id)
    dashboard_main(main_col)

    st.markdown('</div>', unsafe_allow_html=True)