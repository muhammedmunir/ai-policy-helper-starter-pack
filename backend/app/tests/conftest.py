import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rag import RAGEngine

@pytest.fixture(scope="session")
def client():
    return TestClient(app)

@pytest.fixture
def client_fresh():
    """Fresh app instance with empty vector store (no prior ingests)."""
    from app import main as app_module
    original_engine = app_module.engine
    app_module.engine = RAGEngine()
    with TestClient(app) as c:
        yield c
    app_module.engine = original_engine
