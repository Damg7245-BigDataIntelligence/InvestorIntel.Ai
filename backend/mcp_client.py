from modelcontextprotocol import MCPClient

MCP_BASE_URL = "http://localhost:8080"  # Change this!

client = MCPClient(base_url=MCP_BASE_URL)

def get_startup_summary(startup_name: str):
    return client.invoke("get_startup_summary", {"startup_name": startup_name})

def get_industry_report(industry_name: str):
    return client.invoke("get_industry_report", {"industry_name": industry_name})

def get_top_companies(industry_name: str):
    return client.invoke("get_top_companies", {"industry_name": industry_name})

def store_analysis_report(startup_name: str, report_text: str):
    return client.invoke("store_analysis_report", {
        "startup_name": startup_name,
        "report_text": report_text
    })
