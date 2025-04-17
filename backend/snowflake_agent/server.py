from mcp.server.fastmcp import FastMCP
import os
from db_client import SnowflakeDB
from write_detector import SQLWriteDetector

# Initialize FastMCP agent
mcp = FastMCP("Snowflake Agent")

# Load credentials from env
snowflake_config = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database": os.getenv("SNOWFLAKE_DATABASE"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA"),
}

# Init DB + detector
db = SnowflakeDB(snowflake_config)
db.start_init_connection()
write_detector = SQLWriteDetector()

# === TOOLS ===

@mcp.tool()
async def read_query(query: str) -> str:
    """Run SELECT-only query on Snowflake"""
    if write_detector.analyze_query(query)["contains_write"]:
        return "Error: This query includes write operations!"
    try:
        results, _ = await db.execute_query(query)
        return str(results)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def write_query(query: str) -> str:
    """Run INSERT/UPDATE/DELETE query on Snowflake"""
    if not write_detector.analyze_query(query)["contains_write"]:
        return "Error: No write operations detected."
    try:
        results, _ = await db.execute_query(query)
        return f"✅ Query executed: {results}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def describe_table(table_name: str) -> str:
    """Describe schema of a table: format should be DB.SCHEMA.TABLE"""
    try:
        db_name, schema_name, table = table_name.split(".")
        query = f"""
            SELECT column_name, data_type, is_nullable, comment
            FROM {db_name}.information_schema.columns
            WHERE table_schema = '{schema_name.upper()}' AND table_name = '{table.upper()}'
        """
        results, _ = await db.execute_query(query)
        return str(results)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def list_tables(database: str, schema: str) -> str:
    """List tables in a schema"""
    try:
        query = f"""
            SELECT table_name
            FROM {database}.information_schema.tables
            WHERE table_schema = '{schema.upper()}'
        """
        results, _ = await db.execute_query(query)
        return str(results)
    except Exception as e:
        return f"Error: {str(e)}"

# === ENTRYPOINT ===

if __name__ == "__main__":
    mcp.run()
