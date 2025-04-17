from pydantic import BaseModel
from typing import List, Dict, Optional
from typing_extensions import TypedDict


class AnalysisState(TypedDict):
    pdf_file_path: str
    startup_name: str
    industry: str
    linkedin_urls: Optional[List[str]]
    website_url: Optional[str]
    original_filename: Optional[str]
    summary: Dict
    industry_report: str
    competitors: List[Dict]
    final_report: str
    news: List[Dict]

