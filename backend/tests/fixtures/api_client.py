"""Creates a test FastAPI client."""

from fastapi.testclient import TestClient

from app.main import app

api_client = TestClient(app)
