import json
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
import os
import asyncio

MCP_SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../build/index.js"))

server_params = StdioServerParameters(
    command="node",
    args=[MCP_SERVER_PATH],
    env=None
)

async def mcp_search(query: str, num: int = 5):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            print("Initializing session")
            await session.initialize()
            print("Calling tool")
            result = await session.call_tool("search", {"query": query, "num": num})
            print("Result:", result)
            try:
                return json.loads(result.content[0].text)
            except Exception as e:
                print("Error parsing response:", e)
                return []

async def google_search_with_fallback(startup_name, industry):
    """
    Runs a blocking wrapper to call async MCP Google Search tool.
    """
    search_type = "Startup-Specific"
    startup_query = f"recent news or innovations or articles of {startup_name}"
    
    items = await mcp_search(startup_query, num=5)

    # Check relevance
    if not any(startup_name.lower() in (item["title"] + item["snippet"]).lower() for item in items):
        search_type = "Industry-Based"
        industry_query = f"{industry} industry trends recent news US market"
        items = await mcp_search(industry_query, num=5)

    return {"results": items}, search_type

# if __name__ == "__main__":
#     async def main():
#         result, kind = await google_search_with_fallback("OpenAI", "AI")
#         for i, r in enumerate(result["results"], 1):
#             print(f"{i}. {r['title']} ({r['link']})")

#     asyncio.run(main())
