from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import shutil
import json
import sys
import logging
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_debug.log')
    ]
)
logger = logging.getLogger("InvestorIntel-API")

# Import functions from the existing summary.py file
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from summary import upload_to_s3, summarize_pitch_deck_with_gemini, validate_environment
from embedding_manager import EmbeddingManager
from gemini_assistant import GeminiAssistant

logger.info("=== Starting InvestorIntel API ===")

# Get environment variables
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')
S3_REGION = os.getenv('S3_REGION')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

logger.debug(f"GEMINI_MODEL: {GEMINI_MODEL}")
logger.debug(f"AWS_S3_BUCKET_NAME: {AWS_S3_BUCKET_NAME}")
logger.debug(f"S3_REGION: {S3_REGION}")

# Initialize managers
embedding_manager = None
gemini_assistant = None

try:
    logger.info("Initializing EmbeddingManager")
    embedding_manager = EmbeddingManager()
    logger.info("Embedding manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize embedding manager: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"Warning: Failed to initialize embedding manager. Pinecone functionality will be disabled: {e}")

try:
    logger.info("Initializing GeminiAssistant")
    gemini_assistant = GeminiAssistant()
    logger.info("Gemini assistant initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini assistant: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"Warning: Failed to initialize Gemini assistant. AI analysis will be disabled: {e}")

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
    logger.info("Root endpoint called")
    return {"message": "Welcome to the InvestorIntel API"}

@app.get("/health")
async def health_check():
    """Check if the API is running and all required environment variables are set."""
    logger.info("Health check endpoint called")
    
    is_valid, missing_vars = validate_environment()
    
    embedding_status = "active" if embedding_manager else "disabled"
    gemini_status = "active" if gemini_assistant else "disabled"
    
    logger.info(f"Health check - Embedding: {embedding_status}, Gemini: {gemini_status}")
    
    if not is_valid:
        logger.warning(f"Missing environment variables: {missing_vars}")
        return {
            "status": "warning",
            "message": f"API is running but missing environment variables: {', '.join(missing_vars)}",
            "embedding_status": embedding_status,
            "gemini_status": gemini_status
        }
    
    return {
        "status": "ok",
        "message": "API is running and all required environment variables are set",
        "embedding_status": embedding_status,
        "gemini_status": gemini_status
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
    logger.info(f"Processing pitch deck: {file.filename}")
    logger.info(f"Startup: {startup_name}, Industry: {industry}")
    
    # Parse the LinkedIn URLs from JSON string if provided
    linkedin_urls_list = []
    if linkedin_urls:
        try:
            linkedin_urls_list = json.loads(linkedin_urls)
            logger.debug(f"LinkedIn URLs: {linkedin_urls_list}")
        except json.JSONDecodeError as e:
            # If not valid JSON, treat it as a single URL
            linkedin_urls_list = [linkedin_urls]
            logger.debug(f"Parsed LinkedIn URL as single: {linkedin_urls}")
    
    # Get the original filename
    original_filename = file.filename
    logger.debug(f"Original filename: {original_filename}")
    
    # Set default values if not provided
    startup_name = startup_name or "Unknown"
    industry = industry or "Unknown"
    
    # Check if required environment variables are set
    is_valid, missing_vars = validate_environment()
    if not is_valid:
        logger.error(f"Missing environment variables: {missing_vars}")
        raise HTTPException(
            status_code=500, 
            detail=f"Server configuration error: Missing environment variables: {', '.join(missing_vars)}"
        )
    
    # Create a temporary directory to store the uploaded file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary filename for local storage
        temp_filename = f"temp_pitch_deck.pdf"
        file_path = os.path.join(temp_dir, temp_filename)
        logger.debug(f"Temporary file path: {file_path}")
        
        # Save the uploaded file to the temporary directory
        try:
            logger.debug("Saving uploaded file to temporary directory")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(f"Failed to save file: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Upload the file to S3 with the improved naming function
        try:
            logger.info("Uploading file to S3")
            s3_location = upload_to_s3(
                file_path=file_path,
                bucket_name=AWS_S3_BUCKET_NAME,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region=S3_REGION,
                startup_name=startup_name,
                industry=industry,
                original_filename=original_filename
            )
            
            if not s3_location:
                logger.error("S3 upload failed, no location returned")
                raise HTTPException(status_code=500, detail="Failed to upload file to S3")
                
            logger.info(f"File uploaded successfully to S3: {s3_location}")
        except Exception as e:
            logger.error(f"S3 upload error: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"S3 upload error: {str(e)}")
        
        # Generate summary using Gemini
        try:
            logger.info("Generating summary using Gemini")
            investor_summary = summarize_pitch_deck_with_gemini(
                file_path=file_path,
                api_key=os.getenv("GEMINI_API_KEY"),
                model_name=GEMINI_MODEL
            )
            
            if not investor_summary:
                logger.error("Failed to generate summary, empty response")
                raise HTTPException(status_code=500, detail="Failed to generate summary")
                
            logger.info("Summary generated successfully")
            logger.debug(f"Summary preview: {investor_summary[:300]}...")
        except Exception as e:
            logger.error(f"Summary generation error: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Summary generation error: {str(e)}")
        
        # Store embedding in Pinecone if available
        embedding_status = "skipped"
        if embedding_manager:
            try:
                logger.info("Storing embeddings in Pinecone")
                embedding_success = embedding_manager.store_summary_embeddings(
                    summary=investor_summary,
                    startup_name=startup_name,
                    industry=industry,
                    linkedin_urls=linkedin_urls_list,
                    original_filename=original_filename,
                    s3_location=s3_location
                )
                embedding_status = "success" if embedding_success else "failed"
                logger.info(f"Embedding status: {embedding_status}")
            except Exception as e:
                logger.error(f"Error storing embedding: {str(e)}")
                logger.error(traceback.format_exc())
                embedding_status = "error"
        else:
            logger.info("Embedding manager not available, skipping embedding storage")
        
        # Return the results
        logger.info("Returning results")
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
    startup_name: str = None,
    top_k: int = 5,
    generate_ai_response: bool = True
):
    """
    Search for similar startups based on a query and optional filters.
    
    - query: The search query
    - industry: Filter by industry (optional)
    - invested: Filter by investment status ('yes' or 'no', optional)
    - startup_name: Filter by startup name (optional)
    - top_k: Number of results to return (default: 5)
    - generate_ai_response: Whether to generate an AI response using Gemini (default: True)
    """
    logger.info(f"Search startups endpoint called - Query: '{query}'")
    logger.info(f"Filters - Industry: {industry}, Invested: {invested}, Startup: {startup_name}, Top K: {top_k}")
    logger.info(f"Generate AI response: {generate_ai_response}")
    
    if not embedding_manager:
        logger.error("Embedding manager not available")
        raise HTTPException(
            status_code=503,
            detail="Embedding functionality is not available. Check if Pinecone API key is configured."
        )
    
    try:
        # Search for startups
        logger.info("Searching for startups in Pinecone")
        results = embedding_manager.search_similar_startups(
            query=query,
            industry=industry,
            invested=invested,
            startup_name=startup_name,
            top_k=top_k
        )
        
        logger.info(f"Found {len(results)} results")
        
        # Generate AI answer if requested and Gemini assistant is available
        ai_answer = None
        if generate_ai_response and results and gemini_assistant:
            logger.info("Generating AI answer with Gemini")
            
            # Log first result for debugging
            if results:
                first_result = results[0]
                result_id = first_result.get("id", "unknown_id")
                result_score = first_result.get("score", 0)
                result_startup = first_result.get("startup_name", "unknown")
                logger.debug(f"First result - ID: {result_id}, Score: {result_score}, Startup: {result_startup}")
                # Check if text field exists and is not empty
                result_text = first_result.get("text", "")
                if not result_text:
                    logger.warning(f"First result has empty text field: {first_result}")
                else:
                    logger.debug(f"First result text preview: {result_text[:200]}...")
            
            # Process with Gemini
            ai_answer = gemini_assistant.process_query_with_results(
                query=query,
                search_results=results
            )
            
            # Log AI answer
            if ai_answer:
                logger.info("AI answer generated successfully")
                logger.debug(f"AI answer preview: {ai_answer[:300]}...")
            else:
                logger.warning("Empty AI answer returned from Gemini")
        elif not generate_ai_response:
            logger.info("AI response generation disabled by user")
        elif not results:
            logger.info("No search results found, skipping AI response generation")
        elif not gemini_assistant:
            logger.info("Gemini assistant not available, skipping AI response generation")
        
        # Return results
        response_data = {
            "results": results,
            "count": len(results),
            "query": query,
            "filters": {
                "industry": industry,
                "invested": invested,
                "startup_name": startup_name
            }
        }
        
        # Only add ai_answer if it exists
        if ai_answer:
            response_data["ai_answer"] = ai_answer
            logger.debug("Added AI answer to response")
        else:
            logger.debug("No AI answer added to response")
        
        logger.info("Returning search results")
        return response_data
    
    except Exception as e:
        logger.error(f"Error searching startups: {str(e)}")
        logger.error(traceback.format_exc())
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
    logger.info(f"Update investment status - Startup: {startup_name}, Status: {status}")
    
    if not embedding_manager:
        logger.error("Embedding manager not available")
        raise HTTPException(
            status_code=503,
            detail="Embedding functionality is not available. Check if Pinecone API key is configured."
        )
    
    if status not in ["yes", "no"]:
        logger.error(f"Invalid status value: {status}")
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'yes' or 'no'"
        )
    
    try:
        logger.info(f"Updating investment status for {startup_name} to {status}")
        success = embedding_manager.update_investment_status(
            startup_name=startup_name,
            status=status
        )
        
        if not success:
            logger.warning(f"No records found for startup: {startup_name}")
            raise HTTPException(
                status_code=404,
                detail=f"No records found for startup: {startup_name}"
            )
        
        logger.info(f"Successfully updated investment status")
        return {
            "message": f"Successfully updated investment status to '{status}' for {startup_name}",
            "startup_name": startup_name,
            "status": status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating investment status: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error updating investment status: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server")
    uvicorn.run(app, host="0.0.0.0", port=8000)