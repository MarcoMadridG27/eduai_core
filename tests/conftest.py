import os
import sys
from unittest.mock import MagicMock

# Transparent decorator to replace retry.Retry
def dummy_retry(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

# Create a mock module for google.api_core.retry
mock_retry_module = MagicMock()
mock_retry_module.Retry = dummy_retry
sys.modules['google.api_core.retry'] = mock_retry_module

# Mock google.genai
mock_genai = MagicMock()
sys.modules['google.genai'] = mock_genai
sys.modules['google.genai.types'] = MagicMock()

# Configure mock google to return mock_retry_module when accessed
mock_google = MagicMock()
mock_google.__path__ = []  # Mark it as a package

mock_api_core = MagicMock()
mock_api_core.__path__ = []
mock_api_core.retry = mock_retry_module

mock_google.api_core = mock_api_core
mock_google.genai = mock_genai
sys.modules['google'] = mock_google
sys.modules['google.api_core'] = mock_api_core

# Mock chromadb with a real class for EmbeddingFunction to avoid MagicMock inheritance issues
class DummyEmbeddingFunction:
    pass

mock_chromadb = MagicMock()
mock_chromadb.EmbeddingFunction = DummyEmbeddingFunction
sys.modules['chromadb'] = mock_chromadb

# Set environment variables for testing
os.environ["GOOGLE_API_KEY"] = "fake-api-key"

import pytest

@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    test_db = "test_lesson_memory.db"
    
    # Force DB_NAME in both config and database modules
    monkeypatch.setattr("config.DB_NAME", test_db)
    monkeypatch.setattr("database.DB_NAME", test_db)
    
    # Delete test DB if it exists to start fresh
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except:
            pass
            
    # Re-initialize DB
    from database import init_db
    init_db()
    
    yield
    
    # Clean up after test
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except:
            pass
