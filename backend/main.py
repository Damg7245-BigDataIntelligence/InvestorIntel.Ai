from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph_builder import build_analysis_graph
from pinecone_pipeline.embedding_manager import EmbeddingManager
from startup_check import startup_exists_check, StartupCheckRequest
import os
import tempfile
import shutil
import json
import traceback
from typing import List, Optional

app = FastAPI(
    title="InvestorIntel API",
    description="API for processing startup pitch decks and generating investor summaries",
    version="1.0.0"
)

# Create the langgraph
graph = build_analysis_graph()

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
            print("Initial state:", initial_state)
            # Invoke the graph with our initial state
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
                "news": result.get("news")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")