from dotenv import load_dotenv
import snowflake.connector
load_dotenv()
import os


# Load environment variables and set up Snowflake connection
def account_login():
    # Snowflake connection details
    SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")  # e.g. 'vwcoqxf-qtb83828'
    SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")  # Your Snowflake username
    SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")  # Your Snowflake password
    SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE")  # Your role, e.g., 'SYSADMIN'

    print(SNOWFLAKE_ROLE)

    # Connecting to Snowflake
    conn = snowflake.connector.connect(
        user=SNOWFLAKE_USER,        # This should be your username
        password=SNOWFLAKE_PASSWORD,       # This should be your password
        account=SNOWFLAKE_ACCOUNT,     # This should be your Snowflake account URL
        role=SNOWFLAKE_ROLE          # Optional, if you need to specify the role
    )

    cur = conn.cursor()
    print("Connected to Snowflake",cur)

    cur.execute("USE WAREHOUSE INVESTOR_INTEL_WH;")  # Specify the warehouse
    cur.execute("USE DATABASE INVESTOR_INTEL_DB;")  # Specify the database
    conn.commit()

    return conn, cur