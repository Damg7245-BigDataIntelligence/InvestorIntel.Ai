from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import shutil
import json
import sys
from pathlib import Path

# Import functions from the existing summary.py file
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from summary import upload_to_s3, summarize_pitch_deck_with_gemini, validate_environment
from embedding_manager import EmbeddingManager

# Get environment variables (these will be used only when an upload is processed)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
AWS_REGION = os.getenv('AWS_REGION')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

# Initialize embedding manager
embedding_manager = None
try:
    embedding_manager = EmbeddingManager()
except Exception as e:
    print(f"Warning: Failed to initialize embedding manager. Pinecone functionality will be disabled: {e}")

app = FastAPI(
    title="InvestorIntel API",
    description="API for processing startup pitch decks and generating investor summaries",
    version="1.0.0"
)

# Add CORS middleware to allow requests from the Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the InvestorIntel API"}

@app.get("/health")
async def health_check():
    """Check if the API is running and all required environment variables are set."""
    is_valid, missing_vars = validate_environment()
    
    embedding_status = "active" if embedding_manager else "disabled"
    
    if not is_valid:
        return {
            "status": "warning",
            "message": f"API is running but missing environment variables: {', '.join(missing_vars)}",
            "embedding_status": embedding_status
        }
    
    return {
        "status": "ok",
        "message": "API is running and all required environment variables are set",
        "embedding_status": embedding_status
    }

@app.post("/process-pitch-deck")
async def process_pitch_deck(
    file: UploadFile = File(...),
    startup_name: str = Form(None),
    industry: str = Form(None),
    linkedin_urls: str = Form(None)
):
    """
    Process a pitch deck PDF and generate an investor summary.
    
    - file: The pitch deck PDF file
    - startup_name: Name of the startup
    - industry: Industry category
    - linkedin_urls: LinkedIn URLs as a JSON string
    """
    # Parse the LinkedIn URLs from JSON string if provided
    linkedin_urls_list = []
    if linkedin_urls:
        try:
            linkedin_urls_list = json.loads(linkedin_urls)
        except json.JSONDecodeError as e:
            # If not valid JSON, treat it as a single URL
            linkedin_urls_list = [linkedin_urls]
    
    # Get the original filename
    original_filename = file.filename
    print(f"Original filename: {original_filename}")
    
    # Set default values if not provided
    startup_name = startup_name or "Unknown"
    industry = industry or "Unknown"
    
    print(f"Processing pitch deck: {original_filename}")
    print(f"Startup: {startup_name}, Industry: {industry}")
    
    # Check if required environment variables are set
    is_valid, missing_vars = validate_environment()
    if not is_valid:
        raise HTTPException(
            status_code=500, 
            detail=f"Server configuration error: Missing environment variables: {', '.join(missing_vars)}"
        )
    
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
        
        # Upload the file to S3 with the improved naming function
        try:
            s3_location = upload_to_s3(
                file_path=file_path,
                bucket_name=AWS_S3_BUCKET_NAME,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region=AWS_REGION,
                startup_name=startup_name,
                industry=industry,
                original_filename=original_filename
            )
            
            if not s3_location:
                raise HTTPException(status_code=500, detail="Failed to upload file to S3")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 upload error: {str(e)}")
        
        # Generate summary using Gemini
        try:
            investor_summary = summarize_pitch_deck_with_gemini(
                file_path=file_path,
                api_key=GEMINI_API_KEY,
                model_name=GEMINI_MODEL
            )
            
            if not investor_summary:
                raise HTTPException(status_code=500, detail="Failed to generate summary")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summary generation error: {str(e)}")
        
        # Store embeddings in Pinecone if available
        embedding_status = "skipped"
        if embedding_manager:
            try:
                embedding_success = embedding_manager.store_summary_embeddings(
                    summary=investor_summary,
                    startup_name=startup_name,
                    industry=industry,
                    linkedin_urls=linkedin_urls_list,
                    original_filename=original_filename,
                    s3_location=s3_location
                )
                embedding_status = "success" if embedding_success else "failed"
                print(f"Embedding status: {embedding_status}")
            except Exception as e:
                print(f"Error storing embeddings: {e}")
                embedding_status = "error"
        
        # Return the results
        return {
            "startup_name": startup_name,
            "industry": industry,
            "linkedin_urls": linkedin_urls_list,
            "s3_location": s3_location,
            "original_filename": original_filename,
            "summary": investor_summary,
            "embedding_status": embedding_status
        }

@app.get("/search-startups")
async def search_startups(
    query: str,
    industry: str = None,
    invested: str = None,
    top_k: int = 5
):
    """
    Search for similar startups based on a query and optional filters.
    
    - query: The search query
    - industry: Filter by industry (optional)
    - invested: Filter by investment status ('yes' or 'no', optional)
    - top_k: Number of results to return (default: 5)
    """
    if not embedding_manager:
        raise HTTPException(
            status_code=503,
            detail="Embedding functionality is not available. Check if Pinecone API key is configured."
        )
    
    try:
        results = embedding_manager.search_similar_startups(
            query=query,
            industry=industry,
            invested=invested,
            top_k=top_k
        )
        
        return {
            "results": results,
            "count": len(results),
            "query": query,
            "filters": {
                "industry": industry,
                "invested": invested
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching startups: {str(e)}"
        )

@app.post("/update-investment-status")
async def update_investment_status(
    startup_name: str = Form(...),
    status: str = Form("yes")
):
    """
    Update the investment status for a specific startup.
    
    - startup_name: Name of the startup to update
    - status: New investment status (default: 'yes')
    """
    if not embedding_manager:
        raise HTTPException(
            status_code=503,
            detail="Embedding functionality is not available. Check if Pinecone API key is configured."
        )
    
    if status not in ["yes", "no"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'yes' or 'no'"
        )
    
    try:
        success = embedding_manager.update_investment_status(
            startup_name=startup_name,
            status=status
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for startup: {startup_name}"
            )
        
        return {
            "message": f"Successfully updated investment status to '{status}' for {startup_name}",
            "startup_name": startup_name,
            "status": status
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating investment status: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)