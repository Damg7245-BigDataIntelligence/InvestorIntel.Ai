from pydantic import BaseModel
from typing import List, Dict
from typing_extensions import TypedDict


class AnalysisState(TypedDict):
    pdf_file_path: str
    startup_name: str
    summary: Dict
    industry_report: str
    competitors: List[Dict]
    final_report: str

