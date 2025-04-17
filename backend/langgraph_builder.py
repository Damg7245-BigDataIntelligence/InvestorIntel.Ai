from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os
import google.generativeai as genai
from state import AnalysisState
from pinecone_pipeline.summary import summarize_pitch_deck_with_gemini
from pinecone_pipeline.embedding_manager import EmbeddingManager
from s3_utils import upload_pitch_deck_to_s3
import snowflake.connector
from pinecone_pipeline.mcp_google_search_agent import google_search_with_fallback
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Initialize embedding manager
embedding_manager = None
try:
    embedding_manager = EmbeddingManager()
except Exception as e:
    print(f"Warning: Failed to initialize embedding manager. Pinecone functionality will be disabled: {e}")

# -------------------------
# Gemini Prompt Generator
# -------------------------
def generate_gemini_prompt(startup, industry_report, competitors):
    competitor_section = "\n".join([
        f"{c['COMPANY']}: {c['SHORT_DESCRIPTION']} | Revenue: ${c['REVENUE']}, Growth: {c['EMP_GROWTH_PERCENT']}%"
        for c in competitors
    ])

    return f"""
You are a venture capital analyst.

Analyze the following startup and generate a 5–6 page report covering:
1. The problem the startup is solving
2. Whether it is a real, pressing market issue based on Deloitte report
3. Also consider input of competitors short description and revenue growth and employee growth to make a better judgement and also include that in report. Understand properly what competitors are doing based on short description and revenue growth and employee growth.
4. Validation of the claimed market size (compare to Deloitte report if mentioned, else use your own judgement based on the TAM SAM SOM of that industry)
5. Competitor landscape with revenue & employee growth context
6. A recommendation on investment potential with a risk score (1–10)

Startup:
Name: {startup['STARTUP_NAME']}
Industry: {startup['INDUSTRY']}
Summary: {startup['SHORT_DESCRIPTION']}

Industry Trend Report (Deloitte):
{industry_report}

Top 10 Competitors:
{competitor_section}

Output a detailed VC-style strategic report including references to market trends.
Also include a final section: "Market Size Validation & Commentary".
"""

# -------------------------
# Hardcoded Snowflake Logic (MCP-less)
# -------------------------
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")

def snowflake_query(query, params=None):
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
    )
    cursor = conn.cursor()
    cursor.execute(query, params or {})
    result = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in result]

def get_startup_summary(startup_name: str):
    query = """
    SELECT startup_name, industry, short_description 
    FROM INVESTOR_INTEL_DB.PITCH_DECKS.STARTUP_SUMMARY
    WHERE startup_name = %s
    LIMIT 1
    """
    result = snowflake_query(query, (startup_name,))
    return result[0] if result else {"error": "Startup not found."}

def get_industry_report(industry_name: str):
    query = """
    SELECT Report_Summary 
    FROM INVESTOR_INTEL_DB.MARKET_RESEARCH.INDUSTRY_REPORTS 
    WHERE Industry_Name = %s
    LIMIT 1
    """
    result = snowflake_query(query, (industry_name,))
    return result[0]["REPORT_SUMMARY"] if result else "No report found."

def get_top_companies(industry_name: str):
    query = """
    SELECT Company, Industry, Emp_Growth_Percent, Revenue, Short_Description 
    FROM INVESTOR_INTEL_DB.GROWJO_SCHEMA.COMPANY_MERGED_VIEW
    WHERE Industry = %s
    ORDER BY Revenue DESC, Emp_Growth_Percent DESC
    LIMIT 10
    """
    result = snowflake_query(query, (industry_name,))
    return result

def store_analysis_report(startup_name: str, report_text: str):
    query = """
    UPDATE INVESTOR_INTEL_DB.PITCH_DECKS.STARTUP_SUMMARY
    SET analysis_report = %s
    WHERE startup_name = %s
    """
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database="INVESTOR_INTEL_DB"
    )
    cursor = conn.cursor()
    cursor.execute(query, (report_text, startup_name))
    conn.commit()
    return {"status": "success", "message": f"Report stored for {startup_name}"}

# -------------------------
# PDF Processing Node
# -------------------------
def process_pitch_deck(state):
    """Process a pitch deck PDF and generate a summary"""
    print("Processing pitch deck state:", state)
    # Debug printing to help diagnose the issue
    print(f"State keys: {list(state.keys())}")
    print(f"PDF file path in state: {state.get('pdf_file_path')}")
    
    if not state.get("pdf_file_path"):
        print("No PDF file path provided")
        state["error"] = "No PDF file path provided"
        return state
    
    # Check if the file exists
    file_path = state["pdf_file_path"]
    if not os.path.exists(file_path):
        print(f"File doesn't exist at path: {file_path}")
        state["error"] = f"File doesn't exist at path: {file_path}"
        return state
        
    try:
        print(f"Processing file: {file_path}")
        # Extract variables from state
        startup_name = state.get("startup_name", "Unknown")
        industry = state.get("industry", "Unknown")
        linkedin_urls = state.get("linkedin_urls", [])
        website_url = state.get("website_url", "")
        original_filename = state.get("original_filename", os.path.basename(file_path))
        
        print(f"Uploading file to S3 for {startup_name} in {industry}")
        # Upload file to S3
        s3_location = upload_pitch_deck_to_s3(
            file_path=file_path,
            startup_name=startup_name,
            industry=industry,
            original_filename=original_filename
        )
        
        print(f"S3 Upload result: {s3_location}")
        if not s3_location:
            state["error"] = "Failed to upload file to S3"
            return state
            
        state["s3_location"] = s3_location
        
        print(f"Generating summary using Gemini for {file_path}")
        # Generate summary using Gemini
        investor_summary = summarize_pitch_deck_with_gemini(
            file_path=file_path,
            api_key=GEMINI_API_KEY,
            model_name="gemini-2.0-flash"
        )
        
        print(f"Summary generation complete: {investor_summary is not None}")
        if not investor_summary:
            state["error"] = "Failed to generate summary"
            return state
            
        # state["summary_text"] = investor_summary
        
        # Store embedding in Pinecone if available
        if embedding_manager:
            embedding_success = embedding_manager.store_summary_embeddings(
                summary=investor_summary,
                startup_name=startup_name,
                industry=industry,
                website_url=website_url,
                linkedin_urls=linkedin_urls,
                original_filename=original_filename,
                s3_location=s3_location
            )
            state["embedding_status"] = "success" if embedding_success else "failed"
        else:
            state["embedding_status"] = "skipped"
            
        # Update the summary state for subsequent nodes
        # Create the summary object in the format expected by other nodes
        state["summary"] = {
            "STARTUP_NAME": startup_name,
            "INDUSTRY": industry,
            "SHORT_DESCRIPTION": investor_summary
        }
        
        return state
        
    except Exception as e:
        import traceback
        print(f"Error processing pitch deck: {str(e)}")
        print(traceback.format_exc())
        state["error"] = f"Error processing pitch deck: {str(e)}"
        return state

# -------------------------
# Graph Nodes
# -------------------------
def fetch_summary(state):
    # If we already have a summary from PDF processing, skip fetching
    if state.get("summary") and isinstance(state["summary"], dict):
        return state
        
    summary_data = get_startup_summary(state["startup_name"])
    state["summary"] = summary_data
    return state

def fetch_industry_report(state):
    if not state.get("summary") or not isinstance(state["summary"], dict):
        state["industry_report"] = "No industry report available - summary data missing"
        return state
    
    industry = state["summary"].get("INDUSTRY")
    if not industry:
        state["industry_report"] = "No industry report available - industry not specified"
        return state
        
    report = get_industry_report(industry)
    state["industry_report"] = report
    return state

def fetch_competitors(state):
    if not state.get("summary") or not isinstance(state["summary"], dict):
        state["competitors"] = []
        return state
    
    industry = state["summary"].get("INDUSTRY")
    if not industry:
        state["competitors"] = []
        return state
        
    competitors = get_top_companies(industry)
    state["competitors"] = competitors
    return state

def generate_report(state):
    # Check if we have the necessary data
    if not state.get("summary") or not state.get("industry_report") or not state.get("competitors"):
        state["final_report"] = "Unable to generate report: Missing required data"
        return state
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = generate_gemini_prompt(
        startup=state["summary"],
        industry_report=state["industry_report"],
        competitors=state["competitors"]
    )
    response = model.generate_content(prompt)
    final_report = response.text
    state["final_report"] = final_report
    return state

def store_report(state):
    if not state.get("startup_name") or not state.get("final_report"):
        return state
        
    store_analysis_report(state["startup_name"], state["final_report"])
    return state

async def fetch_news(state):
    """Fetch news using the websearch agent and store in Snowflake"""
    if not state.get("summary") or not isinstance(state["summary"], dict):
        state["news"] = "No news available - summary data missing"
        return state
    
    startup_name = state["summary"].get("STARTUP_NAME")
    industry = state["summary"].get("INDUSTRY")
    
    if not startup_name or not industry:
        state["news"] = "No news available - startup name or industry not specified"
        return state
    
    # Call the websearch agent
    results, search_type = await google_search_with_fallback(startup_name, industry)
    news_content = "\n".join([f"{r.get('title', '')}: {r.get('url', '')}" for r in results.get("results", [])])
    
    # Store the news in the state
    state["news"] = news_content
    print("news_content", news_content)
    # Update the Snowflake table with the news
    store_news_in_snowflake(startup_name, news_content)
    
    return state

def store_news_in_snowflake(startup_name: str, news: str):
    """Store the news in the Snowflake table"""
    query = """
    UPDATE INVESTOR_INTEL_DB.PITCH_DECKS.STARTUP_SUMMARY
    SET news = %s
    WHERE startup_name = %s
    """
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database="INVESTOR_INTEL_DB"
    )
    cursor = conn.cursor()
    cursor.execute(query, (news, startup_name))
    conn.commit()
    cursor.close()
    conn.close()

# -------------------------
# Graph Compiler
# -------------------------

def build_analysis_graph():
    builder = StateGraph(AnalysisState)
    print("Building analysis graph")
    # Add nodes
    builder.add_node("process_pitch_deck", process_pitch_deck)
    builder.add_node("fetch_summary", fetch_summary)
    builder.add_node("fetch_industry_report", fetch_industry_report)
    builder.add_node("fetch_competitors", fetch_competitors)
    builder.add_node("generate_report", generate_report)
    builder.add_node("store_report", store_report)
    builder.add_node("fetch_news", fetch_news)  # New node for fetching news

    # Set conditional starting point
    builder.set_conditional_entry_point(
        lambda state: "process_pitch_deck" if state.get("pdf_file_path") else "fetch_summary"
    )
    
    # Add edges
    builder.add_edge("process_pitch_deck", "fetch_summary")
    builder.add_edge("fetch_summary", "fetch_industry_report")
    builder.add_edge("fetch_industry_report", "fetch_competitors")
    builder.add_edge("fetch_competitors", "generate_report")
    builder.add_edge("generate_report", "store_report")
    builder.add_edge("store_report", "fetch_news")  # Add edge to fetch news
    builder.add_edge("fetch_news", END)  # End after fetching news

    return builder.compile()
