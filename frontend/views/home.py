import streamlit as st
import os 
from PIL import Image
import base64
import sys

# Dynamically add project root (InvestorIntel.Ai/) to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ✅ Now do the imports
from backend.database import investor_auth, investorIntel_entity

def render():
    # Session state defaults
    st.session_state.setdefault("user_type", None)
    st.session_state.setdefault("show_signup", False)

    # Layout
    col1, col2 = st.columns([1, 3], gap="large")

    # 🚪 Left Sidebar – Role Selection
    with col1:
        # 🔷 Add Logo
        logo_path = os.path.join("frontend/assets", "InvestorIntel_Logo.png")
        logo = Image.open(logo_path)
        # Convert image to base64
        with open(logo_path, "rb") as f:
            encoded_logo = base64.b64encode(f.read()).decode()

        # Render centered image using HTML
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; padding-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_logo}" width="300">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("## 👋 Welcome")
        st.markdown("### Select Your Role")
        if st.button("🎯 I'm a Startup"):
            st.session_state.user_type = "Startup"
            st.session_state.show_signup = False  # reset view
        if st.button("💼 I'm an Investor"):
            st.session_state.user_type = "Investor"
            st.session_state.show_signup = False

    # 🖥️ Right Content – Info + Forms
    with col2:
        st.markdown("## 🚀 Welcome to InvestorIntel.ai")
        st.markdown("""
        InvestorIntel.ai is your bridge between visionary startups and smart investors.

        - **For Startups**: Submit your pitch deck and attract funding from top-tier investors.
        - **For Investors**: Discover high-potential startups, analyze metrics, and make informed decisions.

        Choose your role from the left to get started!
        """)

        # -------- STARTUP SECTION --------
        if st.session_state.user_type == "Startup":
            st.markdown("---")
            st.markdown("### 🚀 Pitch Deck Upload for Startups")
            st.markdown("""
            Upload your startup details and pitch deck. Our AI system will match your venture with relevant investors based on industry, growth metrics, and more.
            """)
            name = st.text_input("Startup Name")
            email = st.text_input("Contact Email")
            pitch = st.file_uploader("Upload Pitch Deck", type=["pdf", "pptx"])
            if st.button("Submit"):
                if name and email and pitch:
                    st.success("✅ Pitch deck uploaded successfully!")
                else:
                    st.error("⚠️ Please fill out all fields.")

        # -------- INVESTOR SECTION --------
        elif st.session_state.user_type == "Investor":
            st.markdown("---")
            st.markdown("### 💼 Investor Login / Signup")
            st.markdown("""
            Log in to explore the startup ecosystem or sign up to get started. Your dashboard gives you access to filtered startup data and pitch decks.
            """)

            if not st.session_state.show_signup:
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.button("Login"):
                    if username and password:
                        response = investor_auth.login_investor(username, password)
                        if response["status"] == "success":
                            st.session_state.is_logged_in = True
                            st.session_state.username = response.get("username", "")
                            st.session_state.page = "investor_dashboard"
                            st.success(f"✅ Welcome, {st.session_state.username}!")
                            st.experimental_rerun()
                        else:
                            st.error(f"❌ {response['message']}")
                    else:
                        st.error("⚠️ Enter both username and password.")
                
                st.markdown("Don't have an account?")
                if st.button("Go to Signup"):
                    st.session_state.show_signup = True
                    st.experimental_rerun()
            else:
                st.markdown("### 📝 Create Your Investor Account")
                first_name = st.text_input("First Name")
                last_name = st.text_input("Last Name")
                username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                
                if st.button("Sign Up"):
                    if all([first_name, last_name, username, new_email, new_password]):
                        response = investor_auth.signup_investor(first_name, last_name, username, new_email, new_password)
                        if response["status"] == "success":
                            st.success("🎉 Account created! Please log in.")
                            investorIntel_entity.insert_investor(first_name, last_name, new_email, username)
                            st.session_state.show_signup = False
                            st.experimental_rerun()
                        else:
                            st.error(f"❌ {response['message']}")
                    else:
                        st.error("⚠️ Fill out all fields.")
                
                if st.button("Back to Login"):
                    st.session_state.show_signup = False
                    st.experimental_rerun()
