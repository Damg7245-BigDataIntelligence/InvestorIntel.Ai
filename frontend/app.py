import streamlit as st
import requests
import os
import base64
import io
import json
from PIL import Image

# Set page configuration
st.set_page_config(
    page_title="InvestorIntel",
    page_icon="📊",
    layout="wide"
)

# Create a function to encode the image to base64
def get_image_base64(image_path):
    img = Image.open(image_path)
    buffered = io.BytesIO()
    img.save(buffered, format=img.format)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

# Custom CSS for styling
def apply_custom_styling():
    st.markdown("""
    <style>
    .main-header {
        font-size: 42px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 10px;
    }
    .sidebar-content {
        padding: 20px;
    }
    .stButton>button {
        width: 100%;
        background-color: #1E3A8A;
        color: white;
    }
    .search-header {
        font-size: 24px;
        font-weight: bold;
        margin-top: 30px;
    }
    .search-result {
        background-color: #f5f7ff;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        border-left: 4px solid #1E3A8A;
    }
    </style>
    """, unsafe_allow_html=True)

# Apply custom styling
apply_custom_styling()

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'upload'  # Default page

# Create sidebar with logo and title
with st.sidebar:
    st.markdown('<div class="main-header">InvestorIntel</div>', unsafe_allow_html=True)
    
    # This is a placeholder for logo - in production, replace with actual logo path
    # For now, we'll use a placeholder emoji
    st.markdown("📊", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Navigation
    st.subheader("Navigation")
    if st.button("📤 Upload Pitch Deck"):
        st.session_state.page = 'upload'
    if st.button("🔍 Search Startups"):
        st.session_state.page = 'search'
    if st.button("💼 Update Investment Status"):
        st.session_state.page = 'invest'

    st.markdown("---")
    
    # Only show these inputs on the upload page
    if st.session_state.page == 'upload':
        # Industry selection
        st.subheader("Select Industry")
        industry = st.selectbox(
            "Industry",
            options=["Travel", "Food", "Marketing", "Health/Wellness", "Transportation"]
        )
        
        # Startup name
        st.subheader("Startup Information")
        startup_name = st.text_input("Startup Name")
        
        # LinkedIn URL(s)
        st.subheader("LinkedIn URLs")
        linkedin_urls = []
        num_urls = st.number_input("Number of LinkedIn URLs", min_value=1, max_value=5, value=1)
        
        for i in range(int(num_urls)):
            url = st.text_input(f"LinkedIn URL {i+1}", key=f"url_{i}")
            if url:
                linkedin_urls.append(url)

# UPLOAD PAGE
if st.session_state.page == 'upload':
    st.title("Pitch Deck Analysis")
    st.write("Upload your pitch deck PDF for intelligent analysis and investor-ready summaries.")

    # File uploader for pitch deck
    uploaded_file = st.file_uploader("Upload Pitch Deck (PDF)", type=["pdf"])

    if uploaded_file is not None:
        # Display the uploaded file info
        file_details = {"FileName": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": f"{uploaded_file.size / 1024:.2f} KB"}
        st.write(file_details)
        
        # Process button
        if st.button("Process Pitch Deck"):
            with st.spinner('Processing your pitch deck...'):
                try:
                    # Prepare data for API request
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    
                    # Prepare form data
                    form_data = {
                        "startup_name": startup_name if startup_name else "Unknown",
                        "industry": industry,
                        "linkedin_urls": json.dumps(linkedin_urls)
                    }
                    
                    # Print debug info
                    st.info(f"Sending file: {uploaded_file.name}")
                    st.info(f"Startup: {startup_name}, Industry: {industry}")
                    
                    # Send to FastAPI backend
                    response = requests.post(
                        "http://localhost:8000/process-pitch-deck",
                        files=files,
                        data=form_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # Display the summary
                        st.success("Pitch deck processed successfully!")
                        st.subheader("Investor Summary")
                        st.markdown(result["summary"])
                        
                        # Display S3 location info
                        st.subheader("Storage Information")
                        st.info(f"PDF stored at: {result['s3_location']}")
                        
                        # Display the original filename if available
                        if "original_filename" in result:
                            st.info(f"Original filename: {result['original_filename']}")
                        
                        # Display embedding status
                        if "embedding_status" in result:
                            embedding_status = result["embedding_status"]
                            if embedding_status == "success":
                                st.success("✅ Embeddings successfully stored in Pinecone")
                            elif embedding_status == "failed":
                                st.warning("⚠️ Failed to store embeddings in Pinecone")
                            elif embedding_status == "skipped":
                                st.info("ℹ️ Embedding storage skipped - Pinecone not configured")
                            else:
                                st.error(f"❌ Error storing embeddings: {embedding_status}")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# SEARCH PAGE
elif st.session_state.page == 'search':
    st.title("Search Startup Database")
    st.write("Search for similar startups in our database based on your criteria.")
    
    # Search filters
    col1, col2 = st.columns(2)
    
    with col1:
        search_query = st.text_input("Search Query", placeholder="Enter keywords to search for...")
        industry_filter = st.selectbox(
            "Filter by Industry",
            options=["All", "Travel", "Food", "Marketing", "Health/Wellness", "Transportation"],
            index=0
        )
    
    with col2:
        investment_status = st.selectbox(
            "Investment Status",
            options=["All", "Yes", "No"],
            index=0
        )
        top_k = st.slider("Number of Results", min_value=1, max_value=20, value=5)
    
    # Search button
    if st.button("Search"):
        if not search_query:
            st.warning("Please enter a search query")
        else:
            with st.spinner('Searching database...'):
                try:
                    # Prepare query parameters
                    params = {
                        "query": search_query,
                        "top_k": top_k
                    }
                    
                    # Add optional filters
                    if industry_filter != "All":
                        params["industry"] = industry_filter
                    
                    if investment_status != "All":
                        params["invested"] = investment_status.lower()
                    
                    # Send to FastAPI backend
                    response = requests.get(
                        "http://localhost:8000/search-startups",
                        params=params
                    )
                    
                    if response.status_code == 200:
                        results = response.json()
                        
                        if not results.get("results"):
                            st.info("No matching startups found. Try adjusting your search criteria.")
                        else:
                            st.success(f"Found {len(results['results'])} matching startups")
                            
                            # Display search results
                            for i, result in enumerate(results["results"]):
                                with st.container():
                                    st.markdown(f"""
                                    <div class="search-result">
                                        <h3>{result.get('startup_name', 'Unknown Startup')}</h3>
                                        <p><strong>Industry:</strong> {result.get('industry', 'Not specified')}</p>
                                        <p><strong>Investment Status:</strong> {'Invested' if result.get('invested') == 'yes' else 'Not Invested'}</p>
                                        <p><strong>Match Score:</strong> {result.get('score', 0):.2f}</p>
                                        <p><strong>Chunk Type:</strong> {result.get('chunk_type', 'Unknown')}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    with st.expander("View Content"):
                                        st.markdown(result.get('content', 'No content available'))
                                    
                                    # Add button to update investment status
                                    if st.button(f"{'✓ Mark as Invested' if result.get('invested') != 'yes' else '✗ Mark as Not Invested'}", key=f"invest_btn_{i}"):
                                        new_status = "no" if result.get('invested') == 'yes' else "yes"
                                        update_response = requests.post(
                                            "http://localhost:8000/update-investment-status",
                                            data={
                                                "startup_name": result.get('startup_name'),
                                                "status": new_status
                                            }
                                        )
                                        if update_response.status_code == 200:
                                            st.success(f"Updated investment status for {result.get('startup_name')}")
                                            st.experimental_rerun()
                                        else:
                                            st.error(f"Failed to update investment status: {update_response.text}")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# INVEST PAGE
elif st.session_state.page == 'invest':
    st.title("Update Investment Status")
    st.write("Update the investment status for startups in your portfolio.")
    
    startup_name = st.text_input("Startup Name", placeholder="Enter the exact name of the startup...")
    status = st.radio("Investment Status", options=["Invested (Yes)", "Not Invested (No)"], index=0)
    
    # Map the radio selection to yes/no
    status_value = "yes" if status == "Invested (Yes)" else "no"
    
    if st.button("Update Status"):
        if not startup_name:
            st.warning("Please enter a startup name")
        else:
            with st.spinner('Updating investment status...'):
                try:
                    # Send to FastAPI backend
                    response = requests.post(
                        "http://localhost:8000/update-investment-status",
                        data={
                            "startup_name": startup_name,
                            "status": status_value
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"Successfully updated {startup_name} to '{status}'")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("---")
st.markdown("© 2025 InvestorIntel - AI-Powered Pitch Deck Analysis")