import os
import traceback
import json
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import re

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
        
        # Minimum relevance threshold
        self.min_relevance_threshold = 0.3
        
        # Configure the Gemini API
        try:
            genai.configure(api_key=self.GEMINI_API_KEY)
            print(f"Gemini API configured successfully with model: {self.model_name}")
        except Exception as e:
            print(f"Failed to configure Gemini API: {str(e)}")
            print(traceback.format_exc())
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
        print("\n" + "="*50)
        print(f"PROCESSING QUERY: '{query}'")
        print(f"TOTAL RESULTS FROM PINECONE: {len(search_results)}")
        
        # If no results, return early
        if not search_results:
            print("NO RESULTS FOUND. NOT QUERYING GEMINI.")
            return "I don't have any information about that in my database. Please try asking a different question."
        
        # Take top 5 results (or fewer if not enough results)
        top_results = search_results[:min(5, len(search_results))]
        
        # Check if the results are actually relevant
        max_score = max([result.get("score", 0) for result in top_results]) if top_results else 0
        
        print(f"HIGHEST RELEVANCE SCORE: {max_score:.4f}")
        
        # If the highest score is below our threshold, don't query Gemini
        if max_score < self.min_relevance_threshold:
            print(f"ALL SCORES BELOW THRESHOLD ({self.min_relevance_threshold}). NOT QUERYING GEMINI.")
            return "I don't have specific information related to that query in my database. Please try asking about a different topic."
        
        # Print debug information (only for console, not sent to Gemini)
        print("\nRESULTS BEING SENT TO GEMINI:")
        total_chars = 0
        for i, result in enumerate(top_results, 1):
            startup = result.get("startup_name", "Unknown")
            score = result.get("score", 0)
            industry = result.get("industry", "Unknown")
            text_length = len(result.get("text", ""))
            total_chars += text_length
            
            print(f"{i}. {startup} (Score: {score:.4f}, Industry: {industry}, Text length: {text_length} chars)")
            
            # Print a short preview of the text
            text_preview = result.get("text", "")[:100] + "..." if len(result.get("text", "")) > 100 else result.get("text", "")
            print(f"   Preview: {text_preview}")
        
        print(f"\nTOTAL DATA BEING SENT TO GEMINI: {total_chars} characters from {len(top_results)} results")
        print("="*50 + "\n")
        
        try:
            # Format the search results into a context string
            context = self._format_search_results(top_results)
            
            prompt = f"""You are an investment analyst assistant. Your task is to provide accurate insights about startups based ONLY on the information provided in the search results below.

QUERY: {query}

SEARCH RESULTS:
{context}

Guidelines:
1. ONLY use information directly present in the search results to answer the query
2. If the search results don't contain information relevant to the query, clearly state what you don't know
3. Format your response as follows:
   - Use simple text with no special formatting
   - For any list items, use a bullet point format with each bullet on its own line
   - Each bullet should start with "• " and have a space after it
   - Make sure all bullet points are properly separated on their own lines
4. Do NOT include any of these phrases in your response:
   - "Based on the search results..."
   - "According to the provided information..."
   - "Result #X states..."
   - ", here's what I know about..."
5. Just provide the direct information without mentioning that it comes from search results
6. Be concise and to the point

YOUR RESPONSE:"""
            
            model = genai.GenerativeModel(self.model_name)
            
            # Set generation config for better output
            generation_config = {
                "temperature": 0.2,  # Lower temperature for more factual responses
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024
            }
            
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Check response
            if not response or not hasattr(response, 'text'):
                print("Received empty response from Gemini API")
                return "I'm having trouble processing your request. Please try again with a different question."
            
            print(f"Generated response of length: {len(response.text)}")
            
            # Clean up the response format
            clean_response = self._clean_response_format(response.text)
            return clean_response
            
        except Exception as e:
            error_msg = f"Error processing query with Gemini: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            return "I'm having trouble processing your request right now. Please try again later or ask a different question."
    
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
            content = result.get("text", "No content available")
            
            # Check if content is empty or None and provide a placeholder
            if not content or content.strip() == "":
                content = "No content available for this startup."
            
            # Format the result without score or length information
            formatted_result = f"""
RESULT #{i}:
Startup: {startup_name}
Industry: {industry}

{content}
---
"""
            formatted_results.append(formatted_result)
        
        # Combine all formatted results into a single string
        context = "\n".join(formatted_results)
        return context
    
    def _clean_response_format(self, text: str) -> str:
        """
        Clean up response formatting for better presentation.
        
        Args:
            text: The raw response from Gemini
            
        Returns:
            str: Cleaned and formatted response
        """
        # Remove any introductory phrases
        text = text.strip()
        
        # List of common introductory phrases to remove
        intros = [
            "Based on the provided search results:",
            "Based on the search results provided:",
            "Here's the information from the search results:",
            "According to the search results:",
            "Here's what I found in the search results:",
            "From the search results:",
            ", here's the information about",
            ", here's what is known about",
            "The search results indicate that",
            "The information available from the search results shows"
        ]
        
        for intro in intros:
            if text.lower().startswith(intro.lower()):
                text = text[len(intro):].strip()
        
        # Remove all result references
        text = re.sub(r'\(Result #\d+\)', '', text)
        text = re.sub(r'\(Source \d+\)', '', text)
        
        # Fix bullet point formatting line by line
        lines = text.split('\n')
        formatted_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                formatted_lines.append('')
                i += 1
                continue
                
            # Fix bullet points at the start of lines
            if line.startswith('*') or line.startswith('-'):
                line = '• ' + line[1:].strip()
                
            # Check for multiple bullets on the same line
            if '• ' in line and not line.startswith('• '):
                # This line has bullets but doesn't start with one
                parts = re.split(r'(• )', line)
                new_parts = []
                
                for j, part in enumerate(parts):
                    if part == '• ' and j > 0 and parts[j-1].strip() and j+1 < len(parts):
                        # This is a bullet in the middle of text
                        new_parts.append('\n• ')
                    else:
                        new_parts.append(part)
                
                line = ''.join(new_parts)
                
            # Add the processed line
            formatted_lines.append(line)
            i += 1
        
        # Join lines and clean up spacing
        text = '\n'.join(formatted_lines)
        
        # Fix any remaining bullet point issues
        text = text.replace('\n• ', '\n• ')  # Ensure consistent spacing
        text = re.sub(r'([^\n])• ', r'\1\n• ', text)  # Add line break before bullets
        text = re.sub(r'\n{3,}', '\n\n', text)  # No more than 2 consecutive line breaks
        
        return text.strip()
    