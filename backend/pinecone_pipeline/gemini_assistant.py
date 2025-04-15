import os
import traceback
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

class GeminiAssistant:
    """
    A class that processes user queries and Pinecone search results with Gemini 2.0
    to generate relevant insights.
    """
    
    def __init__(self):
        """Initialize the GeminiAssistant with API key and model configuration."""
        
        # Load API key from environment variables
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Set default model to Gemini 2.0 Flash
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        
        # Configure the Gemini API
        try:
            genai.configure(api_key=self.GEMINI_API_KEY)
        except Exception as e:
            raise Exception(f"Failed to configure Gemini API: {str(e)}")
    
    def process_query_with_results(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Process a user query along with Pinecone search results to generate insights.
        
        Args:
            query: The user's search query
            search_results: List of search results from Pinecone
            
        Returns:
            str: Gemini's response based on the query and search results
        """
        # Log search result IDs for debugging
        result_ids = [result.get("id", "unknown_id") for result in search_results]
        try:
            # Format the search results into a context string
            context = self._format_search_results(search_results)
            
            prompt = f"""You are an investment analyst assistant. Answer the following query based ONLY on the information provided from the search results below.

QUERY: {query}

SEARCH RESULTS:
{context}

Based solely on the information in the search results above, provide a comprehensive answer to the query. 
Focus only on information directly relevant to the query. 
If the search results don't contain enough information to answer the query, clearly state what information is missing.
"""
            model = genai.GenerativeModel(self.model_name)
            
            response = model.generate_content(prompt)
            
            # Check response
            if not response or not hasattr(response, 'text'):
                return "Error: Received empty response from Gemini API."
            
            return response.text
            
        except Exception as e:
            error_msg = f"Error processing query with Gemini: {str(e)}"
            return error_msg
    
    def _format_search_results(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Format search results from Pinecone into a context string for Gemini.
        
        Args:
            search_results: List of search results from Pinecone
            
        Returns:
            str: Formatted context string
        """
        formatted_results = []
        
        for i, result in enumerate(search_results, 1):
            # Extract key information from the result
            startup_name = result.get("startup_name", "Unknown")
            industry = result.get("industry", "Unknown Industry")
            invested = "Yes" if result.get("invested") == "yes" else "No"
            similarity = result.get("score", 0)
            content = result.get("text", "No content available")
            
            
            # Check if content is empty or None
            if not content or content.strip() == "":
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
        
        # Combine all formatted results into a single string
        context = "\n".join(formatted_results)
        return context