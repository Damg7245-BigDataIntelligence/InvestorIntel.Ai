import streamlit as st
import requests
import os
import base64
import io
import json
import traceback
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
    .ai-analysis {
        background-color: #f0f7ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1E88E5;
        margin-bottom: 30px;
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
                                st.success("✅ Embedding successfully stored in Pinecone")
                            elif embedding_status == "failed":
                                st.warning("⚠️ Failed to store embedding in Pinecone")
                            elif embedding_status == "skipped":
                                st.info("ℹ️ Embedding storage skipped - Pinecone not configured")
                            else:
                                st.error(f"❌ Error storing embedding: {embedding_status}")
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.exception(e)

# SEARCH PAGE
elif st.session_state.page == 'search':
    st.title("Search Startup Database")
    st.write("Search for similar startups in our database based on your criteria.")
    
    # Debug expander for troubleshooting
    with st.expander("Debug Information", expanded=False):
        st.write("This section shows debugging information for troubleshooting.")
        st.write("Check this area if search results or AI analysis are not displaying correctly.")
        if 'debug_info' in st.session_state:
            st.json(st.session_state.debug_info)
        else:
            st.write("No debug information available yet.")
    
    # Initialize session state for startup list if not exists
    if 'startup_list' not in st.session_state:
        st.session_state.startup_list = []
        # Fetch startup list by using the existing search endpoint with a generic query
        try:
            with st.status("Fetching startup list..."):
                # Use a simple query that would match most documents
                response = requests.get(
                    "http://localhost:8000/search-startups",
                    params={"query": "startup", "top_k": 100, "generate_ai_response": False}  # Get up to 100 results
                )
                
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    st.write(f"Found {len(results)} startups.")
                    
                    # Extract unique startup names
                    startup_names = set()
                    for result in results:
                        startup_name = result.get("startup_name")
                        if startup_name:
                            startup_names.add(startup_name)
                    
                    # Add "All" option and sort the list
                    st.session_state.startup_list = ["All"] + sorted(list(startup_names))
                    st.write(f"Extracted {len(startup_names)} unique startup names.")
                else:
                    st.warning(f"Could not fetch startup list from server. Status code: {response.status_code}")
                    st.text(f"Response: {response.text}")
                    st.session_state.startup_list = ["All"]
        except Exception as e:
            st.warning(f"Error fetching startup list: {str(e)}")
            st.session_state.startup_list = ["All"]
    
    # Search filters
    col1, col2 = st.columns(2)
    
    with col1:
        search_query = st.text_input("Search Query", placeholder="Enter keywords to search for...")
        
        # Startup name filter
        startup_filter = st.selectbox(
            "Filter by Startup",
            options=st.session_state.startup_list,
            index=0
        )
        
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
        
        # Option to enable/disable AI response
        generate_ai = st.checkbox("Generate AI Analysis", value=True)
    
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
                        "top_k": top_k,
                        "generate_ai_response": generate_ai
                    }
                    
                    # Add optional filters
                    if industry_filter != "All":
                        params["industry"] = industry_filter
                    
                    if investment_status != "All":
                        params["invested"] = investment_status.lower()
                        
                    if startup_filter != "All":
                        params["startup_name"] = startup_filter
                    
                    # Display request info for debugging
                    with st.status("Sending search request to API..."):
                        st.write(f"Endpoint: http://localhost:8000/search-startups")
                        st.write(f"Parameters: {params}")
                        
                        # Send to FastAPI backend
                        response = requests.get(
                            "http://localhost:8000/search-startups",
                            params=params
                        )
                        
                        # Store the response for debugging
                        st.session_state.debug_info = {
                            "request": {
                                "url": "http://localhost:8000/search-startups",
                                "params": params
                            },
                            "response": {
                                "status_code": response.status_code,
                                "headers": dict(response.headers),
                                "has_ai_answer": "ai_answer" in response.json() if response.status_code == 200 else False
                            }
                        }
                        
                        if response.status_code == 200:
                            results = response.json()
                            
                            # Add full response data for debugging
                            if "debug_info" in st.session_state:
                                st.session_state.debug_info["response"]["data"] = results
                            
                            # Display raw JSON for debugging in the expander
                            st.write("API response received.")
                    
                    # Display raw JSON for debugging
                    with st.expander("View API Response JSON", expanded=False):
                        st.json(results)
                    
                    if not results.get("results"):
                        st.info("No matching startups found. Try adjusting your search criteria.")
                    else:
                        # If AI response is enabled and present in results
                        if generate_ai and "ai_answer" in results and results["ai_answer"]:
                            st.subheader("AI Analysis")
                            st.write("Based on your query and the search results, here's an AI analysis:")
                            
                            # Use custom styled container for AI analysis
                            st.markdown(f"""
                            <div class="ai-analysis">
                            {results["ai_answer"]}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Add a separator
                            st.markdown("---")
                        elif generate_ai:
                            st.warning("AI analysis was requested but not returned in the response.")
                            if "ai_answer" in results:
                                st.write("AI answer field exists but is empty or null.")
                            else:
                                st.write("AI answer field is missing from the response.")
                        
                        # Display search results count
                        st.success(f"Found {len(results['results'])} matching startups")
                        
                        # Display each search result
                        for i, result in enumerate(results["results"]):
                            with st.container():
                                st.markdown(f"""
                                <div class="search-result">
                                    <h3>{result.get('startup_name', 'Unknown Startup')}</h3>
                                    <p><strong>Industry:</strong> {result.get('industry', 'Not specified')}</p>
                                    <p><strong>Investment Status:</strong> {'Invested' if result.get('invested') == 'yes' else 'Not Invested'}</p>
                                    <p><strong>Match Score:</strong> {result.get('score', 0):.2f}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                with st.expander("View Content"):
                                    st.markdown(result.get('text', 'No content available'))
                                
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
                    st.write("Exception details:")
                    st.exception(e)

# INVEST PAGE
elif st.session_state.page == 'invest':
    st.title("Update Investment Status")
    st.write("Update the investment status for startups in your portfolio.")
    
    # Initialize startup list if not exists (reuse the same logic from search page)
    if 'startup_list' not in st.session_state:
        st.session_state.startup_list = []
        try:
            with st.status("Fetching startup list..."):
                response = requests.get(
                    "http://localhost:8000/search-startups",
                    params={"query": "startup", "top_k": 100, "generate_ai_response": False}
                )
                
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    startup_names = set()
                    for result in results:
                        startup_name = result.get("startup_name")
                        if startup_name:
                            startup_names.add(startup_name)
                    
                    st.session_state.startup_list = sorted(list(startup_names))
                else:
                    st.warning("Could not fetch startup list from server.")
                    st.session_state.startup_list = []
        except Exception as e:
            st.warning(f"Error fetching startup list: {str(e)}")
            st.session_state.startup_list = []
    
    # If we have startup names, use a dropdown, otherwise use text input
    if st.session_state.startup_list:
        startup_name = st.selectbox("Startup Name", options=st.session_state.startup_list)
    else:
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
                    st.exception(e)

# Footer
st.markdown("---")
st.markdown("© 2025 InvestorIntel - AI-Powered Pitch Deck Analysis")