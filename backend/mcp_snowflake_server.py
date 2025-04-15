from modelcontextprotocol import MCPServer, Tool
import snowflake.connector
import os

# Env Vars
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE")

# Snowflake connector (you'll switch DB/Schema in SQL fully-qualified table names)
def snowflake_query(query, params=None):
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
    )
    cursor = conn.cursor()
    cursor.execute(query, params or {})
    result = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in result]

# 🧩 Tool 1: Fetch Deloitte Industry Report
@Tool(name="get_industry_report")
def get_industry_report(industry_name: str):
    query = """
    SELECT Report_Summary 
    FROM INDUSTRY_REPORTS.MARKET_RESEARCH.INDUSTRY_REPORTS 
    WHERE Industry_Name = %s
    LIMIT 1
    """
    result = snowflake_query(query, (industry_name,))
    return result[0]["REPORT_SUMMARY"] if result else "No report found for industry."

# 🧩 Tool 2: Fetch Top 10 Competitors
@Tool(name="get_top_companies")
def get_top_companies(industry_name: str):
    query = """
    SELECT Company, Industry, Emp_Growth_Percent, Revenue_Usd, Short_Description 
    FROM INVESTOR_INTEL_DB.GROWJO_SCHEMA.COMPANY_MERGED_VIEW
    WHERE Industry = %s
    ORDER BY Revenue_Usd DESC, Emp_Growth_Percent DESC
    LIMIT 10
    """
    return snowflake_query(query, (industry_name,))

# 🧩 Tool 3: Fetch Startup Summary
@Tool(name="get_startup_summary")
def get_startup_summary(startup_name: str):
    query = """
    SELECT startup_name, industry, short_description 
    FROM INDUSTRY_REPORTS.PITCH_DECKS.STARTUP_SUMMARY
    WHERE startup_name = %s
    LIMIT 1
    """
    result = snowflake_query(query, (startup_name,))
    return result[0] if result else {"error": "Startup not found."}

@Tool(name="store_analysis_report")
def store_analysis_report(startup_name: str, report_text: str):
    query = """
    UPDATE INDUSTRY_REPORTS.PITCH_DECKS.STARTUP_SUMMARY
    SET analysis_report = %s
    WHERE startup_name = %s
    """
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        warehouse=SNOWFLAKE_WAREHOUSE,
    )
    cursor = conn.cursor()
    cursor.execute(query, (report_text, startup_name))
    conn.commit()
    return {"status": "success", "message": f"Report stored for {startup_name}"}

# 🚀 Start MCP Server
if __name__ == "__main__":
    server = MCPServer(
        tools=[get_industry_report, get_top_companies, get_startup_summary, store_analysis_report],
        host="0.0.0.0",
        port=8080
    )
    server.run()