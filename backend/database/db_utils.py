from backend.database.snowflake_connect import account_login
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
def get_investor_by_username(username):
    conn, cur = account_login()
    cur.execute("SELECT * FROM startup_information.investor WHERE username = %s", (username,))
    row = cur.fetchone()
    return dict(zip([desc[0] for desc in cur.description], row))

def get_startups_by_status(investor_id, status):
    conn, cur = account_login()
    query = """
        SELECT s.startup_id, s.startup_name
        FROM startup_information.startup_investor_map m
        JOIN startup_information.startup s ON m.startup_id = s.startup_id
        WHERE m.investor_id = %s AND m.status = %s
    """
    cur.execute(query, (investor_id, status))
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["startup_id", "startup_name"])

def get_startup_info_by_id(startup_id):
    conn, cur = account_login()
    cur.execute("SELECT * FROM startup_information.startup WHERE startup_id = %s", (startup_id,))
    row = cur.fetchone()
    return dict(zip([desc[0] for desc in cur.description], row))
