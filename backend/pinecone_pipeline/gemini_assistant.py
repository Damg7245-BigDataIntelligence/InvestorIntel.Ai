import os
import logging
import traceback
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gemini_debug.log')
    ]
)
logger = logging.getLogger("GeminiAssistant")

# Load environment variables
load_dotenv()

class GeminiAssistant:
    """
    A class that processes user queries and Pinecone search results with Gemini 2.0
    to generate relevant insights.
    """
    
    def __init__(self):
        """Initialize the GeminiAssistant with API key and model configuration."""
        logger.info("=== Initializing GeminiAssistant ===")
        
        # Load API key from environment variables
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        logger.debug(f"API key loaded: {'PRESENT' if self.GEMINI_API_KEY else 'MISSING'}")
        
        if not self.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY environment variable is not set")
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Set default model to Gemini 2.0 Flash
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(f"Using Gemini model: {self.model_name}")
        
        # Configure the Gemini API
        try:
            genai.configure(api_key=self.GEMINI_API_KEY)
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def process_query_with_results(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Process a user query along with Pinecone search results to generate insights.
        
        Args:
            query: The user's search query
            search_results: List of search results from Pinecone
            
        Returns:
            str: Gemini's response based on the query and search results
        """
        logger.info(f"=== Processing query with Gemini: '{query}' ===")
        logger.info(f"Number of search results: {len(search_results)}")
        
        # Log search result IDs for debugging
        result_ids = [result.get("id", "unknown_id") for result in search_results]
        logger.info(f"Result IDs: {result_ids}")
        
        try:
            # Format the search results into a context string
            logger.debug("Formatting search results into context")
            context = self._format_search_results(search_results)
            
            # Log the first 500 characters of the context for debugging
            logger.debug(f"Context preview (first 500 chars): {context[:500]}...")
            
            # Create the prompt for Gemini
            logger.debug("Creating prompt for Gemini")
            prompt = f"""You are an investment analyst assistant. Answer the following query based ONLY on the information provided from the search results below.

QUERY: {query}

SEARCH RESULTS:
{context}

Based solely on the information in the search results above, provide a comprehensive answer to the query. 
Focus only on information directly relevant to the query. 
If the search results don't contain enough information to answer the query, clearly state what information is missing.
"""
            logger.debug(f"Prompt length: {len(prompt)} characters")
            
            # Send the prompt to Gemini
            logger.info(f"Sending prompt to Gemini model: {self.model_name}")
            model = genai.GenerativeModel(self.model_name)
            
            logger.debug("Calling Gemini API with prompt")
            response = model.generate_content(prompt)
            
            # Check response
            if not response or not hasattr(response, 'text'):
                logger.error("Received empty or invalid response from Gemini")
                return "Error: Received empty response from Gemini API."
            
            # Log response
            logger.info("Successfully received response from Gemini")
            logger.debug(f"Response preview: {response.text[:300]}...")
            
            return response.text
            
        except Exception as e:
            error_msg = f"Error processing query with Gemini: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return error_msg
    
    def _format_search_results(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Format search results from Pinecone into a context string for Gemini.
        
        Args:
            search_results: List of search results from Pinecone
            
        Returns:
            str: Formatted context string
        """
        logger.debug("Formatting search results for Gemini")
        formatted_results = []
        
        for i, result in enumerate(search_results, 1):
            # Extract key information from the result
            startup_name = result.get("startup_name", "Unknown")
            industry = result.get("industry", "Unknown Industry")
            invested = "Yes" if result.get("invested") == "yes" else "No"
            similarity = result.get("score", 0)
            content = result.get("text", "No content available")
            
            logger.debug(f"Formatting result {i}: {startup_name} ({similarity:.2f})")
            
            # Check if content is empty or None
            if not content or content.strip() == "":
                logger.warning(f"Empty content for result {i}: {startup_name}")
                content = "No content available for this startup."
            
            # Format the result
            formatted_result = f"""
RESULT #{i}:
Startup: {startup_name}
Industry: {industry}
Invested: {invested}
Relevance Score: {similarity:.2f}

{content}
---
"""
            formatted_results.append(formatted_result)
            logger.debug(f"Added formatted result {i}, length: {len(formatted_result)} chars")
        
        # Combine all formatted results into a single string
        context = "\n".join(formatted_results)
        logger.debug(f"Total context length: {len(context)} characters")
        return context

# Test function
if __name__ == "__main__":
    print("Testing GeminiAssistant with sample data...")
    
    try:
        # Create instance
        assistant = GeminiAssistant()
        
        # Sample data
        query = "What are some promising SaaS business models in the marketing industry?"
        search_results = [
            {
                "startup_name": "MarketingAI",
                "industry": "Marketing",
                "invested": "no",
                "score": 0.95,
                "text": "**Business Model:** SaaS subscription with tiered pricing based on features and user count. Freemium entry tier with basic functionality. Enterprise tier with custom integrations.\n\n**Target Market:** Mid-sized marketing agencies spending >$5k/month on software. Market estimated at $2.5B globally."
            },
            {
                "startup_name": "ContentFlow",
                "industry": "Marketing",
                "invested": "yes",
                "score": 0.85,
                "text": "**Business Model:** Hybrid SaaS model with core platform subscription plus usage-based billing for AI content generation. Average contract value $3,200/month.\n\n**Traction:** 45% MoM growth, 93% retention rate, current ARR $1.2M."
            }
        ]
        
        # Process query with results
        response = assistant.process_query_with_results(query, search_results)
        
        # Print response
        print("\nGemini Response:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        print(traceback.format_exc())