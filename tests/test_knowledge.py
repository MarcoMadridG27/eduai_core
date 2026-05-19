import pytest
from unittest.mock import MagicMock, patch
import knowledge
from knowledge import GeminiEmbeddingFunction, init_knowledge_base

def test_embedding_function():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1, 0.2, 0.3]
    mock_response.embeddings = [mock_embedding]
    mock_client.models.embed_content.return_value = mock_response
    
    with patch("knowledge.client", mock_client):
        fn = GeminiEmbeddingFunction()
        fn.document_mode = True
        res = fn(["hello"])
        assert res == [[0.1, 0.2, 0.3]]
        
        fn.document_mode = False
        res = fn(["hello"])
        assert res == [[0.1, 0.2, 0.3]]

def test_init_knowledge_base_already_loaded():
    mock_db = MagicMock()
    mock_db.count.return_value = 5
    with patch("knowledge.knowledge_db", mock_db):
        init_knowledge_base()
        mock_db.add.assert_not_called()

def test_init_knowledge_base_success():
    mock_db = MagicMock()
    mock_db.count.return_value = 0
    
    mock_response = MagicMock()
    mock_response.text = "Este es un fragmento de texto bastante largo para que pase la validacion de longitud minima que es de 50 caracteres.\n\nEste es el segundo fragmento de texto largo para la base de conocimientos."
    mock_response.raise_for_status = MagicMock()
    
    with patch("knowledge.knowledge_db", mock_db), \
         patch("requests.get", return_value=mock_response) as mock_get, \
         patch("time.sleep", MagicMock()):
        init_knowledge_base()
        mock_get.assert_called_once()
        assert mock_db.add.called

def test_init_knowledge_base_error():
    mock_db = MagicMock()
    mock_db.count.return_value = 0
    
    with patch("knowledge.knowledge_db", mock_db), \
         patch("requests.get", side_effect=Exception("Connection error")):
        # Should not raise exception, but catch it and log it
        init_knowledge_base()
