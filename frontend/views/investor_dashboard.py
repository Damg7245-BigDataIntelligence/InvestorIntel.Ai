import streamlit as st

def render():
    if not st.session_state.get("is_logged_in"):
        st.warning("You must log in first.")
        st.session_state.page = "home"
        st.experimental_rerun()

    col1, col2 = st.columns([9, 1])
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.page = "home"
            st.session_state.is_logged_in = False
            st.experimental_rerun()

    st.title("📊 Investor Dashboard")
    st.write("Welcome! Here’s your private dashboard to explore startups, insights, and more.")
