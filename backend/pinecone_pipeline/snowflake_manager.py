import os
import logging
import uuid
from snowflake.connector import connect
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('snowflake.log')
    ]
)
logger = logging.getLogger("SnowflakeManager")

# Load environment variables
load_dotenv()

class SnowflakeManager:
    """Class to manage Snowflake operations for startup summaries"""
    
    def __init__(self):
        logger.info("Initializing SnowflakeManager")
        
        # Get Snowflake credentials from environment
        self.account = os.getenv('SNOWFLAKE_ACCOUNT')
        self.user = os.getenv('SNOWFLAKE_USER')
        self.password = os.getenv('SNOWFLAKE_PASSWORD')
        self.role = os.getenv('SNOWFLAKE_ROLE')
        self.warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        self.database = os.getenv('SNOWFLAKE_DATABASE')
        
        # Validate credentials
        if not all([self.account, self.user, self.password, self.warehouse, self.database]):
            logger.error("Missing required Snowflake credentials")
            raise ValueError("Missing required Snowflake credentials")
            
        # Initialize Snowflake objects
        self.initialize_snowflake_objects()
        
    def get_connection(self):
        """Create and return a Snowflake connection"""
        return connect(
            account=self.account,
            user=self.user,
            password=self.password,
            role=self.role,
            warehouse=self.warehouse,
            database=self.database
        )
        
    def initialize_snowflake_objects(self):
        """Initialize Snowflake database, schema, and table"""
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # Create database if not exists
            cur.execute(f"""
            CREATE DATABASE IF NOT EXISTS {self.database}
            """)
            
            # Create schema if not exists
            cur.execute("""
            CREATE SCHEMA IF NOT EXISTS PITCH_DECKS
            """)
            
            # Create table if not exists
            cur.execute("""
            CREATE TABLE IF NOT EXISTS PITCH_DECKS.STARTUP_SUMMARY (
                STARTUP_ID VARCHAR(36) PRIMARY KEY,
                STARTUP_NAME VARCHAR(255) NOT NULL,
                INDUSTRY VARCHAR(255),
                SHORT_DESCRIPTION TEXT,
                ANALYSIS_REPORT TEXT,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                S3_LOCATION VARCHAR(1000),
                ORIGINAL_FILENAME VARCHAR(255)
            )
            """)
            
            logger.info("Successfully initialized Snowflake objects")
            
        except Exception as e:
            logger.error(f"Error initializing Snowflake objects: {e}")
            raise
        finally:
            cur.close()
            conn.close()
            
    def store_startup_summary(self, 
                            startup_name: str,
                            summary: str,
                            industry: str = None,
                            s3_location: str = None,
                            original_filename: str = None) -> str:
        """
        Store startup summary in Snowflake
        
        Args:
            startup_name: Name of the startup
            summary: Generated summary from Gemini
            industry: Industry category
            s3_location: S3 URI of the stored PDF
            original_filename: Original filename of the PDF
            
        Returns:
            startup_id: Generated UUID for the startup
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            # Generate a unique ID for the startup
            startup_id = str(uuid.uuid4())
            
            # Insert the summary into Snowflake
            cur.execute("""
            INSERT INTO PITCH_DECKS.STARTUP_SUMMARY (
                STARTUP_ID,
                STARTUP_NAME,
                INDUSTRY,
                SHORT_DESCRIPTION,
                S3_LOCATION,
                ORIGINAL_FILENAME
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                startup_id,
                startup_name,
                industry or "Unknown",
                summary,
                s3_location,
                original_filename
            ))
            
            conn.commit()
            logger.info(f"Successfully stored summary for startup: {startup_name}")
            
            return startup_id
            
        except Exception as e:
            logger.error(f"Error storing startup summary: {e}")
            raise
        finally:
            cur.close()
            conn.close() 