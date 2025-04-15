import os
import logging
import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from .snowflake_manager import SnowflakeManager
# Load environment variables
load_dotenv()

class EmbeddingManager:
    """
    Class to manage embeddings for pitch deck summaries using the Monolithic Chunking
    strategy where each summary is treated as a single, complete unit.
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
        try:
            self.snowflake_manager = SnowflakeManager()
            print("Snowflake manager initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Snowflake manager: {e}")
            self.snowflake_manager = None
    
    def create_chunks_from_summary(self, summary: str) -> List[Dict[str, str]]:
        """
        Divide the summary into two logical chunks with clear separation of content.
        """        
        # Define the sections for each chunk with clear separation
        business_chunk_headers = [
            "Problem", "Solution", "Product/Service", "Business Model", 
            "Target Market", "Opportunity", "Traction", "Milestones", "Competition"
        ]
        
        team_chunk_headers = [
            "Team", "Financials", "Funding Ask", "Use of Funds", "Investment", "Investor Synopsis"
        ]
        
        # Split the summary into lines
        lines = summary.split('\n')
        
        # Initialize containers for each chunk's content
        business_content = []
        team_content = []
        current_chunk = None
        
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
                
            # Check if this line starts a new section
            is_section_header = any(header in stripped_line for header in business_chunk_headers + team_chunk_headers)
            
            if is_section_header:
                # Determine which chunk this section belongs to
                if any(header in stripped_line for header in business_chunk_headers):
                    current_chunk = "business"
                elif any(header in stripped_line for header in team_chunk_headers):
                    current_chunk = "team"
            
            # Add content to appropriate chunk
            if current_chunk == "business":
                business_content.append(stripped_line)
            elif current_chunk == "team":
                team_content.append(stripped_line)
        
        # Create the final chunks
        chunks = [
            {
                "type": "Business Overview & Market Opportunity",
                "content": "\n".join(business_content) if business_content else "No business overview information found."
            },
            {
                "type": "Team & Investment Details",
                "content": "\n".join(team_content) if team_content else "No team or investment information found."
            }
        ]
        
        # Log chunk information
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i+1} ({chunk['type']}) length: {len(chunk['content'])} characters")
            print(f"Chunk {i+1} content preview: {chunk['content'][:150]}...")
        
        return chunks
    
    def store_summary_embeddings(self, 
                               summary: str, 
                               startup_name: str,
                               industry: str,
                               website_url: str,
                               linkedin_urls: List[str],
                               original_filename: str,
                               s3_location: str) -> bool:
        """Modified to store in both Pinecone and Snowflake"""
        print(f"Storing data for {startup_name} pitch deck")
        
        try:
            # Store in Snowflake first
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
                except Exception as e:
                    print(f"Failed to store in Snowflake: {e}")
                    startup_id = None
            
            # Create chunks and store in Pinecone
            chunks = self.create_chunks_from_summary(summary)
            
            if not chunks:
                print("No chunks created from summary")
                return False
            
            # Current timestamp for the upload
            timestamp = datetime.datetime.now().isoformat()
            print(f"Upload timestamp: {timestamp}")
            
            # Generate a unique ID for this record - using _1 suffix to match original format
            unique_id = f"{startup_name.replace(' ', '_')}_{timestamp}_1"
            print(f"Creating embedding with ID: {unique_id}")
            
            # Generate embedding for the content
            print(f"Generating embedding")
            embedding = self.model.encode(summary).tolist()
            print(f"Generated embedding with {len(embedding)} dimensions")
            
            # Prepare metadata - maintain the exact same format as before
            metadata = {
                "startup_name": startup_name,
                "industry": industry,
                "linkedin_urls": "|".join(linkedin_urls) if linkedin_urls else "",
                "chunk_type": "Complete Pitch Deck Summary",  # Set to Complete Pitch Deck Summary for all startups
                "original_filename": original_filename,
                "s3_location": s3_location,
                "upload_timestamp": timestamp,
                "invested": "no",  # Default to 'no' as specified
                "text": summary  # Store the complete summary
            }
            
            # Log metadata for debugging
            print(f"Metadata: startup={startup_name}, industry={industry}, chunk_type={metadata['chunk_type']}")
            
            # Insert into Pinecone
            print(f"Inserting into Pinecone with ID: {unique_id}")
            self.index.upsert([(unique_id, embedding, metadata)])
            print(f"Successfully inserted into Pinecone")
            
            return True
        
        except Exception as e:
            print(f"Error storing data: {e}", exc_info=True)
            return False
    
    def search_similar_startups(self, query: str, industry: str = None, invested: str = None, 
                           startup_name: str = None, top_k: int = 5):
        """
        Search for similar startups based on a query and optional filters.
        
        Args:
            query: The search query text
            industry: Filter by industry category (optional)
            invested: Filter by investment status ('yes' or 'no', optional)
            startup_name: Filter by startup name (optional)
            top_k: Number of results to return
            
        Returns:
            List of dictionary results with startup information
        """
        print(f"Searching for startups with query: '{query}'")
        print(f"Filters - Industry: {industry}, Invested: {invested}, Startup: {startup_name}, Top K: {top_k}")
        
        try:
            # Generate embedding for the query
            query_embedding = self.model.encode(query).tolist()
            
            # Prepare filter if industry or invested filters are provided
            filter_dict = {}
            if industry:
                filter_dict["industry"] = {"$eq": industry}
            if invested:
                filter_dict["invested"] = {"$eq": invested}
            if startup_name:
                filter_dict["startup_name"] = {"$eq": startup_name}
            
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
                
                # Create and add result entry - maintain all original fields
                result = {
                    "id": match["id"],
                    "startup_name": metadata.get("startup_name"),
                    "industry": metadata.get("industry"),
                    "s3_location": metadata.get("s3_location"),
                    "chunk_type": metadata.get("chunk_type"),
                    "score": score,
                    "invested": metadata.get("invested"),
                    "linkedin_urls": metadata.get("linkedin_urls", ""),
                    "original_filename": metadata.get("original_filename", ""),
                    "upload_timestamp": metadata.get("upload_timestamp", ""),
                    "text": metadata.get("text", "No content available")
                }
                processed_results.append(result)
                
                # Log each match
            
            return processed_results
        
        except Exception as e:
            return []

    def update_investment_status(self, startup_name: str, status: str = "yes"):
        """
        Update the investment status for a specific startup.
        
        Args:
            startup_name: Name of the startup to update
            status: New investment status (default: 'yes')
            
        Returns:
            bool: True if successful, False otherwise
        """
        
        try:
            # Fetch all records for this startup
            print(f"Fetching records for startup: {startup_name}")
            query_embedding = self.model.encode("dummy query for fetching records").tolist()
            results = self.index.query(
                vector=query_embedding,
                top_k=100,  # Fetch a large number to get all records
                include_metadata=True,
                filter={"startup_name": {"$eq": startup_name}}
            )
            
            # Extract IDs of matched records
            matches = results.get("matches", [])
            ids_to_update = [match["id"] for match in matches]
            print(f"Found {len(ids_to_update)} records to update")
            
            if not ids_to_update:
                print(f"No records found for startup: {startup_name}")
                return False
            
            # Update each record with the new investment status
            for record_id in ids_to_update:
                print(f"Updating record with ID: {record_id}")
                
                # Fetch the current record to get its vector and metadata
                records = self.index.fetch([record_id])
                if not records or record_id not in records["vectors"]:
                    print(f"Failed to fetch record with ID: {record_id}")
                    continue
                
                record = records["vectors"][record_id]
                vector = record["values"]
                metadata = record["metadata"]
                
                # Log the current investment status
                print(f"Changing investment status from '{metadata.get('invested', 'unknown')}' to '{status}'")
                
                # Update the invested status
                metadata["invested"] = status
                
                # Upsert the updated record
                self.index.upsert([(record_id, vector, metadata)])
                print(f"Successfully updated record: {record_id}")
            
            print(f"Updated investment status to '{status}' for {len(ids_to_update)} records of {startup_name}")
            return True
        
        except Exception as e:
            print(f"Error updating investment status: {e}", exc_info=True)
            return False

# Add a test function that can be run directly
if __name__ == "__main__":
    # More detailed logging when run as a script
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('embedding_test.log')
        ]
    )
    
    print("=" * 50)
    print("Testing EmbeddingManager (Monolithic Chunking Strategy)")
    print("=" * 50)
    
    try:
        # Initialize the manager
        print("\n1. Initializing EmbeddingManager")
        manager = EmbeddingManager()
        
        # Check connection to Pinecone
        print("\n2. Testing Pinecone connection")
        stats = manager.index.describe_index_stats()
        print(f"Connected to Pinecone index: {manager.index_name}")
        print(f"Index Stats: {stats}")
        
        # Test with a sample summary
        print("\n3. Testing with sample summary")
        sample_summary = """
        **Problem:** Managing content marketing at scale is complex and inefficient.
        
        **Solution:** Contentools provides a centralized platform for content marketing workflows.
        
        **Product/Service:** An all-in-one content marketing platform with planning, production, and distribution tools.
        
        **Business Model:** SaaS subscription model with tiered pricing based on features and user count.
        
        **Target Market & Opportunity:** Mid-sized B2B companies spending >$10K/month on content marketing. Market size estimated at $400M.
        
        **Team:** Founded by industry veterans with 10+ years experience in marketing technology.
        
        **Traction/Milestones:** $500K ARR, growing 15% MoM with 85% customer retention rate.
        
        **Competition:** HubSpot and CoSchedule focus on broader marketing needs, while we specialize in content workflows.
        
        **Financials:** $500K current ARR with 75% gross margins and path to profitability in 18 months.
        
        **Funding Ask & Use:** Seeking $2M seed round for product development (40%), sales team expansion (40%), and marketing (20%).
        
        **Investor Synopsis:** Strong product-market fit in growing content marketing space with promising early traction. Experienced team addressing clear pain point with scalable SaaS model.
        """
        
        print(f"\nProcessed summary into a single chunk")
        print("-" * 40)
        print(f"Content length: {len(sample_summary)} characters")
        print(f"Content preview: {sample_summary[:150]}...")
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")