import streamlit as st
import os 
from PIL import Image
import base64
import sys

FAST_API_URL = "http://localhost:8000"

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

            # Initialize once
            for key, default in {
                "startup_name": "",
                "founder_name": "",
                "email_address": "",
                "valuation_ask": 0.0,
                "industry": "",
                "website_url": "",
                "linkedin_url": "",
                "investors": [],
                "pitch_deck_uploaded": False,
                "pitch_deck_file": None
            }.items():
                st.session_state.setdefault(key, default)

            # Form fields
            st.session_state.startup_name = st.text_input("Startup Name", value=st.session_state.startup_name)
            st.session_state.founder_name = st.text_input("Founder Name", value=st.session_state.founder_name)
            st.session_state.email_address = st.text_input("Contact Email", value=st.session_state.email_address)
            st.session_state.valuation_ask = st.number_input("Valuation Ask (USD)", min_value=0.0, format="%.2f", value=st.session_state.valuation_ask)
            st.session_state.industry = st.text_input("Industry", value=st.session_state.industry)

            if not st.session_state.pitch_deck_uploaded:
                uploaded_file = st.file_uploader("Upload Pitch Deck", type=["pdf"])
                if uploaded_file:
                    st.session_state.pitch_deck_file = uploaded_file

            st.session_state.website_url = st.text_input("Website URL", value=st.session_state.website_url)
            st.session_state.linkedin_url = st.text_input("LinkedIn Profile URL", value=st.session_state.linkedin_url)

            investor_options = investorIntel_entity.get_all_investor_usernames()
            
            # Force 'investors' to always be a list
            if not isinstance(st.session_state.get("investors"), list):
                st.session_state.investors = []

            # Now clean defaults
            valid_investor_defaults = [
                label for label in st.session_state.investors
                if label in investor_options
            ]

            # Render dropdown
            selected_labels = st.multiselect(
                "Select Potential Investors",
                options=investor_options,
                default=valid_investor_defaults
            )

            # Save updated selection
            st.session_state.investors = selected_labels

            selected_usernames = [label.split(" (")[0] for label in selected_labels]

            # Handle submit
            if st.button("Submit"):
                missing = []
                if not st.session_state.startup_name: missing.append("Startup Name")
                if not st.session_state.founder_name: missing.append("Founder Name")
                if not st.session_state.email_address: missing.append("Contact Email")
                if not st.session_state.valuation_ask: missing.append("Valuation Ask")
                if not st.session_state.industry: missing.append("Industry")
                if not st.session_state.pitch_deck_file: missing.append("Pitch Deck Document")

                if missing:
                    st.error("⚠️ The following required fields are missing:")
                    for field in missing:
                        st.markdown(f"- ❌ **{field}**")
                else:
                    try:
                        investorIntel_entity.insert_startup(
                            st.session_state.startup_name,
                            st.session_state.founder_name,
                            st.session_state.email_address,
                            st.session_state.website_url,
                            st.session_state.linkedin_url,
                            st.session_state.valuation_ask,
                            st.session_state.industry
                        )
                        investorIntel_entity.map_startup_to_investors(
                            st.session_state.startup_name,
                            selected_usernames
                        )

                        st.session_state.pitch_deck_uploaded = True
                        st.success("✅ Your pitch deck has been submitted successfully! Our team or investors will reach out to you if there's a fit. 🚀")

                        # Clear fields
                        for field in [
                            "startup_name", "founder_name", "email_address", "valuation_ask",
                            "industry", "website_url", "linkedin_url", "investors"
                        ]:
                            st.session_state[field] = "" if isinstance(st.session_state[field], str) else 0.0

                    except Exception as e:
                        st.error(f"❌ Error during submission: {e}")


        # -------- INVESTOR SECTION --------
        elif st.session_state.user_type == "Investor":
            st.markdown("---")
            st.markdown("### 💼 Investor Login / Signup")
            st.markdown("""
            Log in to explore the startup ecosystem or sign up to get started. Your dashboard gives you access to filtered startup data and pitch decks.
            """)

            # Ensure defaults are initialized
            for key, default in {
                "inv_first_name": "",
                "inv_last_name": "",
                "inv_username": "",
                "inv_email": "",
                "inv_password": "",
                "login_username": "",
                "login_password": ""
            }.items():
                st.session_state.setdefault(key, default)

            if not st.session_state.show_signup:
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.button("Login"):
                    if username and password:
                        response = investor_auth.login_investor(username, password)
                        if response["status"] == "success":
                            st.session_state.is_logged_in = True
                            st.session_state.username = response.get("username", "")
                            st.success(f"✅ Welcome, {st.session_state.username}!")

                            # Clear login fields
                            st.session_state.login_username = ""
                            st.session_state.login_password = ""

                            st.session_state.page = "investor_dashboard"
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

                st.session_state.inv_first_name = st.text_input("First Name", value=st.session_state.inv_first_name, key="inv_first_name_field")
                st.session_state.inv_last_name = st.text_input("Last Name", value=st.session_state.inv_last_name, key="inv_last_name_field")
                st.session_state.inv_username = st.text_input("Username", value=st.session_state.inv_username, key="inv_username_field")
                st.session_state.inv_email = st.text_input("Email", value=st.session_state.inv_email, key="inv_email_field")
                st.session_state.inv_password = st.text_input("Password", type="password", value=st.session_state.inv_password, key="inv_password_field")

                if st.button("Sign Up"):
                    if all([st.session_state.inv_first_name, st.session_state.inv_last_name,
                            st.session_state.inv_username, st.session_state.inv_email, st.session_state.inv_password]):
                        response = investor_auth.signup_investor(
                            st.session_state.inv_first_name,
                            st.session_state.inv_last_name,
                            st.session_state.inv_username,
                            st.session_state.inv_email,
                            st.session_state.inv_password
                        )

                        if response["status"] == "success":
                            st.success("🎉 Account created! Please log in.")
                            investorIntel_entity.insert_investor(
                                st.session_state.inv_first_name,
                                st.session_state.inv_last_name,
                                st.session_state.inv_email,
                                st.session_state.inv_username
                            )

                            # Clear sign-up fields
                            for field in ["inv_first_name", "inv_last_name", "inv_username", "inv_email", "inv_password"]:
                                st.session_state[field] = ""

                            st.session_state.show_signup = False
                            st.experimental_rerun()
                        else:
                            st.error(f"❌ {response['message']}")
                    else:
                        st.error("⚠️ Fill out all fields.")

                if st.button("Back to Login"):
                    st.session_state.show_signup = False
                    st.experimental_rerun()
