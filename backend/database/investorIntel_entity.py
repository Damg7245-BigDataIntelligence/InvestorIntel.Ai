from backend.database.snowflake_connect import account_login
from dotenv import load_dotenv

load_dotenv()

def get_context(conn, cur):
    cur.execute("USE ROLE ACCOUNTADMIN;")  # Specify the role
    cur.execute("USE WAREHOUSE INESTOR_INTEL_WH;")  # Specify the warehouse
    cur.execute("USE DATABASE INESTOR_INTEL_DB;")  # Specify the database

    conn.commit()  # Commit the changes
# Function to create the InvestorIntel schema and tables
def create_InvestorIntel_entities(conn, cur):

    # Step 0: Set the context
    get_context(conn, cur)
    print("Context set to Investor Intel database and warehouse.")

    # Step 1: Create Schema
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS startup_information;
    """)
    print("Schema - startup_information: created successfully.")

    # Step 2: Create Investor Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS startup_information.investor (
            investor_id         NUMBER AUTOINCREMENT PRIMARY KEY,
            first_name          STRING,
            last_name           STRING,
            email_address       STRING UNIQUE,
            username            STRING UNIQUE,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("Investor table created successfully.")

    # Step 3: Create Startup Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS startup_information.startup (
            startup_id          NUMBER AUTOINCREMENT PRIMARY KEY,
            startup_name        STRING,
            founder_name        STRING,
            email_address       STRING,
            website_url         STRING,
            linkedin_url        STRING,
            valuation_ask       NUMBER(18, 2),
            pitch_deck_link     STRING,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("Startup table created successfully.")

    # Step 4: Create Bridge Table to map Investors to Startups
    cur.execute("""
        CREATE TABLE IF NOT EXISTS startup_information.startup_investor_map (
            map_id              NUMBER AUTOINCREMENT PRIMARY KEY,
            startup_id          NUMBER,
            investor_id         NUMBER,
            status              STRING DEFAULT 'Not Viewed',  -- Other values: Viewed, Decision Pending, Rejected, Funded
            invested_amount     NUMBER(18, 2),                -- NULL if not funded
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_startup FOREIGN KEY (startup_id)
                REFERENCES startup_information.startup(startup_id),

            CONSTRAINT fk_investor FOREIGN KEY (investor_id)
                REFERENCES startup_information.investor(investor_id)
        );
    """)
    print("Bridge table startup_investor_map created successfully.")
    
    conn.commit()  # Commit the changes
    print("InvestorIntel schema and tables created successfully.")

def insert_investor(first_name, last_name, email_address, username):
    conn, cur = account_login()
    get_context(conn, cur)
    try:
        insert_query = """
            INSERT INTO startup_information.investor (
                first_name,
                last_name,
                email_address,
                username
            )
            VALUES (%s, %s, %s, %s);
        """
        cur.execute(insert_query, (first_name, last_name, email_address, username))
        conn.commit()
        print("✅ Investor inserted successfully.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to insert investor: {e}")

def insert_startup(startup_name, founder_name, email_address, website_url, linkedin_url, valuation_ask, pitch_deck_link):
    conn, cur = account_login()
    get_context(conn, cur)
    try:
        insert_query = """
            INSERT INTO startup_information.startup (
                startup_name,
                founder_name,
                email_address,
                website_url,
                linkedin_url,
                valuation_ask,
                pitch_deck_link
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(insert_query, (
            startup_name,
            founder_name,
            email_address,
            website_url,
            linkedin_url,
            valuation_ask,
            pitch_deck_link
        ))
        conn.commit()
        print("✅ Startup inserted successfully.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to insert startup: {e}")

def map_startup_to_investors(startup_name, investor_usernames):
    conn, cur = account_login()
    get_context(conn, cur)
    try:
        # Step 1: Get startup_id
        cur.execute("""
            SELECT startup_id FROM startup_information.startup
            WHERE LOWER(startup_name) = LOWER(%s);
        """, (startup_name,))
        result = cur.fetchone()
        
        if not result:
            raise ValueError(f"❌ Startup '{startup_name}' not found.")

        startup_id = result[0]

        # Step 2: Get investor_ids for each username
        for username in investor_usernames:
            cur.execute("""
                SELECT investor_id FROM startup_information.investor
                WHERE LOWER(username) = LOWER(%s);
            """, (username,))
            investor_result = cur.fetchone()

            if not investor_result:
                print(f"⚠️ Investor with username '{username}' not found. Skipping.")
                continue

            investor_id = investor_result[0]

            # Step 3: Insert into mapping table
            cur.execute("""
                INSERT INTO startup_information.startup_investor_map (
                    startup_id, investor_id, status, invested_amount
                ) VALUES (%s, %s, 'Not Viewed', NULL);
            """, (startup_id, investor_id))

        conn.commit()
        print("✅ Mapping complete.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to map startup to investors: {e}")

def get_all_investor_usernames():
    conn, cur = account_login()
    get_context(conn, cur)
    try:
        cur.execute("""
            SELECT username FROM startup_information.investor;
        """)
        results = cur.fetchall()
        usernames = [row[0] for row in results]
        return usernames
    except Exception as e:
        print(f"❌ Failed to fetch investor usernames: {e}")
        return []
    


if __name__ == "__main__":
    conn, cur = account_login()
    create_InvestorIntel_entities(conn, cur)
    print("InvestorIntel schema and tables created successfully.")

    # Close the cursor and connection   
    cur.close()
    conn.close()
    print("Snowflake connection closed.")
    # Close the connection  
    
