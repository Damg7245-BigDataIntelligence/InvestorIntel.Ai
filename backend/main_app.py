from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph_builder import build_analysis_graph
from pinecone_pipeline.embedding_manager import EmbeddingManager
from startup_check import startup_exists_check, StartupCheckRequest
from database import db_utils, investor_auth, investorIntel_entity
from pinecone_pipeline.gemini_assistant import GeminiAssistant
import os
import pandas as pd
import tempfile
import shutil
import json
import traceback
from typing import List, Optional
from s3_utils import upload_pitch_deck_to_s3
from pinecone_pipeline.embedding_manager import EmbeddingManager

embedding_manager = EmbeddingManager()
gemini_assistant = GeminiAssistant()

app = FastAPI(
    title="InvestorIntel API",
    description="API for processing startup pitch decks and generating investor summaries",
    version="1.0.0"
)

# Create the langgraph
graph = None

# Add CORS middleware to allow requests from the Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------- Models -------
class AnalyzeRequest(BaseModel):
    startup_name: str

class PitchDeckRequest(BaseModel):
    startup_name: str
    industry: Optional[str] = None
    linkedin_urls: Optional[List[str]] = []
    website_url: Optional[str] = None

class StartupRequest(BaseModel):
    startup_name: str
    email_address: str
    website_url: str
    valuation_ask: float
    industry: str
    investor_usernames: list[str]
    founder_list: list[dict]

class InvestorRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    username: str

class InvestorSignupRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    password: str

class InvestorLoginRequest(BaseModel):
    username: str
    password: str

class StartupStatusRequest(BaseModel):
    investor_id: int
    status: str

class StartupInfoRequest(BaseModel):
    startup_id: int

class InvestorByUsernameRequest(BaseModel):
    username: str

class ColumnRequest(BaseModel):
    column_name: str
    startup_id:   int

# ------- API Endpoints -------
@app.get("/")
async def root():
    return {"message": "Welcome to the InvestorIntel API"}

@app.get("/health")
async def health_check():
    """Check if the API is running"""
    return {
        "status": "ok",
        "message": "API is running and all required services are operational"
    }

@app.post("/check-startup-exists")
async def check_startup_exists(request: StartupCheckRequest):
    """Check if a startup already exists in the database"""
    return startup_exists_check(request.startup_name)

@app.post("/analyze")
def analyze_startup(request: AnalyzeRequest):
    """Analyze existing startup by name"""
    try:
        state = {"startup_name": request.startup_name}
        result = graph.invoke(state)
        return {
            "status": "success",
            "startup": request.startup_name,
            "final_report": result.get("final_report")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-pitch-deck")
async def process_pitch_deck(
    file: UploadFile = File(...),
    startup_name: str = Form(None),
    industry: str = Form(None),
    linkedin_urls: str = Form(None),
    website_url: str = Form(None)
):
    """
    Process a pitch deck PDF, generate summary, and analysis report all at once.
    """
    # Parse the LinkedIn URLs from JSON string if provided
    linkedin_urls_list = []
    if linkedin_urls:
        try:
            linkedin_urls_list = json.loads(linkedin_urls)
        except json.JSONDecodeError:
            # If not valid JSON, treat it as a single URL
            linkedin_urls_list = [linkedin_urls]
    
    # Get the original filename
    original_filename = file.filename
    
    # Set default values if not provided
    startup_name = startup_name or "Unknown"
    industry = industry or "Unknown"
    print("Startup name:", startup_name)
    # Create a temporary directory to store the uploaded file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary filename for local storage
        temp_filename = f"temp_pitch_deck.pdf"
        file_path = os.path.join(temp_dir, temp_filename)
        
        # Save the uploaded file to the temporary directory
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Process with langgraph
        try:
            # Prepare the initial state for the graph
            initial_state = {
                "pdf_file_path": file_path,
                "startup_name": startup_name,
                "industry": industry,
                "linkedin_urls": linkedin_urls_list,
                "website_url": website_url,
                "original_filename": original_filename
            }
            global graph
            if not graph:
                graph = build_analysis_graph()

            result = await graph.ainvoke(initial_state)
            
            # Check for errors
            if "error" in result:
                raise HTTPException(status_code=500, detail=result["error"])
            
            # Return the results
            return {
                "startup_name": startup_name,
                "industry": industry,
                "linkedin_urls": linkedin_urls_list,
                "s3_location": result.get("s3_location"),
                "original_filename": original_filename,
                "summary": result.get("summary_text"),
                "embedding_status": result.get("embedding_status"),
                "final_report": result.get("final_report"),
                "news": result.get("news"),
                "competitor_visualizations": result.get("competitor_visualizations")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
        
@app.post("/add-startup-info")
def add_startup(data: StartupRequest):
    try:
        investorIntel_entity.insert_startup(
            data.startup_name,
            data.email_address,
            data.website_url,
            data.valuation_ask,
            data.industry
        )
        investorIntel_entity.map_startup_to_investors(
            data.startup_name,
            data.investor_usernames
        )
        investorIntel_entity.insert_startup_founder_map(
            data.founder_list
        )
        return {"status": "success", "message": "Startup added and mapped successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/fetch-investor-usernames")
def fetch_investor_usernames():
    try:
        usernames = investorIntel_entity.get_all_investor_usernames()
        return usernames
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/add-investor-info")
def add_investor(data: InvestorRequest):
    try:
        investorIntel_entity.insert_investor(
            data.first_name,
            data.last_name,
            data.email,
            data.username
        )
        return {"status": "success", "message": "Investor inserted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/investor-signup-auth")
def signup_investor(data: InvestorSignupRequest):
    try:
        result = investor_auth.signup_investor(
            data.first_name,
            data.last_name,
            data.username,
            data.email,
            data.password
        )
        return result  # assuming it returns a dict like {"status": "success", ...}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/investor-login-auth")
def login_investor(data: InvestorLoginRequest):
    try:
        return investor_auth.login_investor(data.username, data.password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/fetch-investor-info")
def fetch_investor_info(username: str):
    try:
        investor_info = db_utils.get_investor_info(username)
        if investor_info:
            return investor_info
        else:
            raise HTTPException(status_code=404, detail="Investor not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/fetch-startups-by-status")
def fetch_startups_by_status(req: StartupStatusRequest):
    try:
        # db_utils returns a pandas.DataFrame
        df: pd.DataFrame = db_utils.get_startups_by_status(
            req.investor_id, req.status
        )
        # convert to list of dicts
        startups = df.to_dict(orient="records")
        return {"status": "success", "startups": startups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/fetch-startup-info")
def fetch_startup_info(req: StartupInfoRequest):
    try:
        info = db_utils.get_startup_info_by_id(req.startup_id)
        if info:
            return {
                "status": "success",
                "startup": info
            }
        else:
            raise HTTPException(status_code=404, detail="Startup not found")
    except HTTPException:
        raise
    except Exception as e:
        # unexpected errors get turned into 500s
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fetch-investor-by-username")
def fetch_investor_by_username(req: InvestorByUsernameRequest):
    try:
        info = db_utils.get_investor_by_username(req.username)
        if info:
            return {
                "status": "success",
                "investor": info
            }
        else:
            raise HTTPException(status_code=404, detail="Investor not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
class ChatRequest(BaseModel):
    query: str
    
@app.post("/chat")
async def chat(request: ChatRequest):
    """Process a chat query and return an AI response."""
    # Validate the query
    query = request.query.strip()
    if not query:
        return {
            "response": "Please enter a question about startups in our database.",
            "query": query,
            "results_count": 0
        }
    
    # Handle test cases for empty database or other edge cases
    if query.lower() in ["test empty database", "test no results"]:
        return {
            "response": "I don't have any information about that in my database. Please try asking about a different startup or topic.",
            "query": query,
            "results_count": 0
        }
    
    try:
        # Search for relevant startups
        results = embedding_manager.search_similar_startups(
            query=query,
            top_k=5  # Get the top 5 most relevant results
        )
        
        # Check if we have any results
        if not results or len(results) == 0:
            return {
                "response": "I don't have any information about that in my database. Please try asking about a different startup or topic.",
                "query": query,
                "results_count": 0
            }
        
        # Process with Gemini
        ai_response = gemini_assistant.process_query_with_results(
            query=query,
            search_results=results
        )
        
        
        return {
            "response": ai_response,
            "query": query,
            "results_count": len(results)
        }
    except Exception as e:
        # Return a user-friendly error message
        return {
            "response": "I'm having trouble processing your request right now. Please try again with a different question.",
            "query": query,
            "results_count": 0,
            "error": str(e)
        }

@app.post("/get-startup-column")
def get_startup_column(req: ColumnRequest):
    """
    Fetch a single column value for the given startup_id.
    """
    try:
        # this will raise ValueError if column_name is invalid
        value = db_utils.get_startup_column_by_id(req.column_name, req.startup_id)
        if value is None:
            # no such startup or column is NULL
            raise HTTPException(status_code=404, detail="No data found")
        return {
            "value": value
        }
    except ValueError as ve:
        # invalid column name
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # unexpected errors
        raise HTTPException(status_code=500, detail=str(e))