import pytest
from fastapi.testclient import TestClient
import os
import sys

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(project_root)

from main import app

client = TestClient(app)

# Sample data for testing
SAMPLE_PDF_PATH = "tests/test_data/sample_pitch_deck.pdf"
SAMPLE_STARTUP_NAME = "TestStartup"
SAMPLE_INDUSTRY = "AI"
SAMPLE_LINKEDIN_URLS = '["https://linkedin.com/in/test"]'
SAMPLE_WEBSITE_URL = "https://teststartup.com"

@pytest.fixture(scope="module")
def setup_environment():
    # Set up environment variables for testing
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_S3_BUCKET_NAME"] = "test-bucket"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["SNOWFLAKE_USER"] = "test"
    os.environ["SNOWFLAKE_PASSWORD"] = "test"
    os.environ["SNOWFLAKE_ACCOUNT"] = "test"
    os.environ["SNOWFLAKE_WAREHOUSE"] = "test"
    os.environ["SNOWFLAKE_DATABASE"] = "test_db"
    os.environ["SNOWFLAKE_ROLE"] = "test_role"
    yield
    # Teardown if necessary

def test_process_pitch_deck_integration(setup_environment):
    # Ensure the sample PDF exists
    assert os.path.exists(SAMPLE_PDF_PATH), "Sample PDF file is missing."

    # Simulate a file upload
    with open(SAMPLE_PDF_PATH, "rb") as file:
        response = client.post(
            "/process-pitch-deck",
            files={"file": ("sample_pitch_deck.pdf", file, "application/pdf")},
            data={
                "startup_name": SAMPLE_STARTUP_NAME,
                "industry": SAMPLE_INDUSTRY,
                "linkedin_urls": SAMPLE_LINKEDIN_URLS,
                "website_url": SAMPLE_WEBSITE_URL
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "s3_location" in data
    assert "summary" in data
    assert "final_report" in data