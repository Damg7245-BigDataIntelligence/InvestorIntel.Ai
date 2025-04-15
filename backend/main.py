# main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph_builder import build_analysis_graph

app = FastAPI()
graph = build_analysis_graph()

# 📥 Request model
class AnalyzeRequest(BaseModel):
    startup_name: str

# 🚀 API Endpoint
@app.post("/analyze")
def analyze_startup(request: AnalyzeRequest):
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

# 🔧 Optional direct CLI test
if __name__ == "__main__":
    startup_name = "AirBnB"  # Replace with any test name
    state = {"startup_name": startup_name}
    result = graph.invoke(state)
    print("----- VC-STYLE REPORT START -----")
    print(result["final_report"])
    print("----- VC-STYLE REPORT END -----")
