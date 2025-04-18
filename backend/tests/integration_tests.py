import pytest
from fastapi.testclient import TestClient
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(project_root)

from main import app

client = TestClient(app)

SAMPLE_PDF_PATH = "tests/test_data/sample_pitch_deck.pdf"
SAMPLE_STARTUP_NAME = "TestStartup"
SAMPLE_INDUSTRY = "AI"
SAMPLE_LINKEDIN_URLS = '["https://linkedin.com/in/test"]'
SAMPLE_WEBSITE_URL = "https://teststartup.com"

@pytest.fixture(scope="module")
def setup_environment():
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

@pytest.fixture(autouse=True)
def mock_graph_and_deps():
    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value={
        "s3_location": "https://mock-s3.com/pitchdeck.pdf",
        "summary_text": "This is a mocked summary.",
        "embedding_status": "completed",
        "final_report": "This is a mocked final report.",
        "news": [{"title": "Mock News", "url": "https://mocknews.com"}]
    })
    with patch('main.build_analysis_graph', return_value=fake_graph):
        yield

def test_process_pitch_deck_integration(setup_environment):
    assert os.path.exists(SAMPLE_PDF_PATH), "Sample PDF file is missing."

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
    assert data["s3_location"] == "https://mock-s3.com/pitchdeck.pdf"
    assert data["summary"] == "This is a mocked summary."
    assert data["final_report"] == "This is a mocked final report."

def test_startup_exists_check_integration(setup_environment, mock_graph_and_deps):
    """Test the startup check endpoint"""
    # Patch the startup_exists_check function directly
    with patch('main.startup_exists_check', return_value={"exists": True}):
        response = client.post(
            "/check-startup-exists",
            json={"startup_name": "TestStartup"}
        )
        
        assert response.status_code == 200
        assert response.json().get("exists") is True