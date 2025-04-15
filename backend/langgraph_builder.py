# langgraph_builder.py

from langgraph.graph import StateGraph, END
from mcp_client import (
    get_startup_summary,
    get_industry_report,
    get_top_companies,
    store_analysis_report
)
from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
    
# -------------------------
# Gemini Prompt Generator
# -------------------------
def generate_gemini_prompt(startup, industry_report, competitors):
    competitor_section = "\n".join([
        f"{c['Company']}: {c['Short_Description']} | Revenue: ${c['Revenue_Usd']}, Growth: {c['Emp_Growth_Percent']}%"
        for c in competitors
    ])

    return f"""
You are a venture capital analyst.

Analyze the following startup and generate a 5–6 page report covering:
1. The problem the startup is solving
2. Whether it is a real, pressing market issue based on Deloitte report
3. Validation of the claimed market size (compare to Deloitte report if mentioned, else use your own judgement based on the TAM SAM SOM of that industry)
4. Competitor landscape with revenue & employee growth context
5. A recommendation on investment potential with a risk score (1–10)

Startup:
Name: {startup['startup_name']}
Industry: {startup['industry']}
Summary: {startup['short_description']}

Industry Trend Report (Deloitte):
{industry_report}

Top 10 Competitors:
{competitor_section}

Output a detailed VC-style strategic report including references to market trends.
Also include a final section: "Market Size Validation & Commentary".
"""

# -------------------------
# Graph Nodes
# -------------------------
def fetch_summary(state):
    summary_data = get_startup_summary(state["startup_name"])
    state["summary"] = summary_data
    return state

def fetch_industry_report(state):
    industry = state["summary"]["industry"]
    report = get_industry_report(industry)
    state["industry_report"] = report
    return state

def fetch_competitors(state):
    industry = state["summary"]["industry"]
    competitors = get_top_companies(industry)
    state["competitors"] = competitors
    return state

def generate_report(state):
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = generate_gemini_prompt(
        startup=state["summary"],
        industry_report=state["industry_report"],
        competitors=state["competitors"]
    )
    response = model.generate_content(prompt)
    final_report = response.text
    state["final_report"] = final_report
    return state

def store_report(state):
    store_analysis_report(state["startup_name"], state["final_report"])
    return state

# -------------------------
# Graph Compiler
# -------------------------
def build_analysis_graph():
    builder = StateGraph()

    builder.add_node("fetch_summary", fetch_summary)
    builder.add_node("fetch_industry_report", fetch_industry_report)
    builder.add_node("fetch_competitors", fetch_competitors)
    builder.add_node("generate_report", generate_report)
    builder.add_node("store_report", store_report)

    builder.set_entry_point("fetch_summary")
    builder.add_edge("fetch_summary", "fetch_industry_report")
    builder.add_edge("fetch_industry_report", "fetch_competitors")
    builder.add_edge("fetch_competitors", "generate_report")
    builder.add_edge("generate_report", "store_report")
    builder.add_edge("store_report", END)

    return builder.compile()
