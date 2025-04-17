import os
import logging
import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

# Use absolute import instead of relative import
try:
    from snowflake_manager import SnowflakeManager
except ImportError:
    # Try another import path if the first one fails
    try:
        from pinecone_pipeline.snowflake_manager import SnowflakeManager
    except ImportError:
        print("Warning: SnowflakeManager could not be imported")
        SnowflakeManager = None

# Load environment variables
load_dotenv()

class EmbeddingManager:
    """
    Class to manage embeddings for pitch deck summaries using a single chunk approach.
    """
    
    def __init__(self):
        # Load environment variables
        self.PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
        if not self.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable is not set")
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=self.PINECONE_API_KEY)
        self.index_name = "investor-intel"
        self.dimension = 384  # Matching the embedding model's output size
        
        # Check and create Pinecone index if it doesn't exist
        existing_indexes = [index["name"] for index in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        else:
            print(f"Index '{self.index_name}' already exists.")
        
        # Connect to the index
        self.index = self.pc.Index(self.index_name)
        stats = self.index.describe_index_stats()
        
        # Load Sentence Transformer Model
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        print("Initializing Snowflake manager")
        # Initialize Snowflake manager
        self.snowflake_manager = None
        if SnowflakeManager is not None:
            try:
                self.snowflake_manager = SnowflakeManager()
                print("Snowflake manager initialized successfully")
            except Exception as e:
                print(f"Failed to initialize Snowflake manager: {e}")
    
    def check_startup_exists(self, startup_name: str) -> bool:
        """
        Check if a startup with the given name already exists in the database.
        Case-insensitive search to match "Uber" with "uber", etc.
        
        Args:
            startup_name: Name of the startup to check
            
        Returns:
            bool: True if the startup exists, False otherwise
        """
        if not startup_name:
            return False
            
        try:
            # Since Pinecone doesn't support case-insensitive search directly,
            # we'll fetch all results and then compare case-insensitively
            query_embedding = self.model.encode("dummy query for checking existence").tolist()
            
            # First try an exact match (for efficiency)
            exact_results = self.index.query(
                vector=query_embedding,
                top_k=1,
                include_metadata=True,
                filter={"startup_name": {"$eq": startup_name}}
            )
            
            if exact_results.get("matches", []):
                return True
                
            # If no exact match, get a larger set of results to check case-insensitively
            all_results = self.index.query(
                vector=query_embedding,
                top_k=100,  # Get more results to increase chance of finding a match
                include_metadata=True
            )
            
            matches = all_results.get("matches", [])
            
            # Check each result for a case-insensitive match
            for match in matches:
                metadata = match.get("metadata", {})
                db_startup_name = metadata.get("startup_name", "")
                
                if db_startup_name.lower() == startup_name.lower():
                    print(f"Found case-insensitive match: '{db_startup_name}' matches '{startup_name}'")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking if startup exists: {e}", exc_info=True)
            return False
    
    def store_summary_embeddings(self, 
                               summary: str, 
                               startup_name: str,
                               industry: str,
                               website_url: str,
                               linkedin_urls: List[str],
                               original_filename: str,
                               s3_location: str) -> bool:
        """Store the summary as a single chunk in both Pinecone and Snowflake"""
        print(f"Storing data for {startup_name} pitch deck")
        
        # First check if the startup already exists (case-insensitive)
        if self.check_startup_exists(startup_name):
            print(f"Startup {startup_name} already exists in the database (case-insensitive match)")
            return False
        
        # Store in Snowflake first if available
        snowflake_success = False
        if self.snowflake_manager:
            try:
                startup_id = self.snowflake_manager.store_startup_summary(
                    startup_name=startup_name,
                    summary=summary,
                    industry=industry,
                    website_url=website_url,
                    s3_location=s3_location,
                    original_filename=original_filename
                )
                print(f"Stored summary in Snowflake with ID: {startup_id}")
                snowflake_success = True
            except Exception as e:
                print(f"Failed to store in Snowflake: {e}")
                print("Continuing with Pinecone storage despite Snowflake error")
        
        try:
            # Current timestamp for the upload
            timestamp = datetime.datetime.now().isoformat()
            print(f"Upload timestamp: {timestamp}")
            
            # Generate a unique ID for this record
            unique_id = f"{startup_name.replace(' ', '_')}_{timestamp}"
            print(f"Creating embedding with ID: {unique_id}")
            
            # Generate embedding for the content
            print(f"Generating embedding")
            embedding = self.model.encode(summary).tolist()
            print(f"Generated embedding with {len(embedding)} dimensions")
            
            # Prepare metadata
            metadata = {
                "startup_name": startup_name,
                "industry": industry,
                "linkedin_urls": "|".join(linkedin_urls) if linkedin_urls else "",
                "original_filename": original_filename,
                "s3_location": s3_location,
                "upload_timestamp": timestamp,
                "invested": "no",  # Default to 'no' as specified
                "text": summary,  # Store the complete summary
                "snowflake_status": "success" if snowflake_success else "skipped" 
            }
            
            # Log metadata for debugging
            print(f"Metadata: startup={startup_name}, industry={industry}")
            
            # Insert into Pinecone
            print(f"Inserting into Pinecone with ID: {unique_id}")
            self.index.upsert([(unique_id, embedding, metadata)])
            print(f"Successfully inserted into Pinecone")
            
            return True
        
        except Exception as e:
            print(f"Error storing data in Pinecone: {e}", exc_info=True)
            return False
    
    def search_similar_startups(self, query: str, industry: str = None, top_k: int = 5):
        """
        Search for similar startups based on a query and optional filters.
        
        Args:
            query: The search query text
            industry: Filter by industry category (optional)
            top_k: Number of results to return
            
        Returns:
            List of dictionary results with startup information
        """
        print(f"Searching for startups with query: '{query}'")
        print(f"Filters - Industry: {industry}, Top K: {top_k}")
        
        try:
            # Generate embedding for the query
            query_embedding = self.model.encode(query).tolist()
            
            # Prepare filter if industry filter is provided
            filter_dict = {}
            if industry:
                filter_dict["industry"] = {"$eq": industry}
            
            # Log the filter being used
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict if filter_dict else None
            )
            
            # Process and return results
            matches = results.get("matches", [])
            
            processed_results = []
            for i, match in enumerate(matches):
                metadata = match["metadata"]
                score = match["score"]
                
                # Create and add result entry
                result = {
                    "id": match["id"],
                    "startup_name": metadata.get("startup_name"),
                    "industry": metadata.get("industry"),
                    "s3_location": metadata.get("s3_location"),
                    "score": score,
                    "linkedin_urls": metadata.get("linkedin_urls", ""),
                    "original_filename": metadata.get("original_filename", ""),
                    "upload_timestamp": metadata.get("upload_timestamp", ""),
                    "text": metadata.get("text", "No content available"),
                    "snowflake_status": metadata.get("snowflake_status", "unknown")
                }
                processed_results.append(result)
            
            return processed_results
        
        except Exception as e:
            print(f"Error searching startups: {e}", exc_info=True)
            return []