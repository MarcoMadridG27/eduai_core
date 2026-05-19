import pytest
import json
from unittest.mock import MagicMock, patch
from services import generate_lesson_stream, generate_lesson_result

async def dummy_sleep(*args, **kwargs):
    pass

@pytest.mark.asyncio
async def test_generate_lesson_stream_no_client():
    with patch("services.client", None), \
         patch("asyncio.sleep", dummy_sleep):
        stream = generate_lesson_stream("session-123", "Tema: Multiplicacion")
        chunks = []
        async for chunk in stream:
            chunks.append(json.loads(chunk))
        
        assert chunks[0]["status"] == "progress"
        assert chunks[2]["status"] == "error"
        assert "API Key" in chunks[2]["message"]

@pytest.mark.asyncio
async def test_generate_lesson_stream_success():
    mock_client = MagicMock()
    mock_db = MagicMock()
    
    # Mocking Gemini Client response
    mock_response_core = MagicMock()
    mock_response_core.text = '{"tema": "Multiplicacion", "ciclo": "VI"}'
    
    mock_response_resources = MagicMock()
    mock_response_resources.text = '{"fichasDeTrabajo": []}'
    
    mock_client.models.generate_content.side_effect = [
        mock_response_core,
        mock_response_resources
    ]
    
    mock_db.query.return_value = {"documents": [["doc1", "doc2"]]}
    
    with patch("services.client", mock_client), \
         patch("services.knowledge_db", mock_db), \
         patch("services.save_session_input", MagicMock()), \
         patch("services.update_session_status", MagicMock()), \
         patch("services.save_message", MagicMock()), \
         patch("services.save_generated_session", MagicMock()), \
         patch("asyncio.sleep", dummy_sleep):
        
        stream = generate_lesson_stream("session-123", "Tema: Multiplicacion")
        chunks = []
        async for chunk in stream:
            chunks.append(json.loads(chunk))
            
        assert any(c["status"] == "completed" for c in chunks)
        completed_chunk = next(c for c in chunks if c["status"] == "completed")
        assert completed_chunk["data"]["tema"] == "Multiplicacion"

@pytest.mark.asyncio
async def test_generate_lesson_stream_exception_fase1():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Gemini Down")
    
    with patch("services.client", mock_client), \
         patch("services.save_session_input", MagicMock()), \
         patch("services.update_session_status", MagicMock()), \
         patch("asyncio.sleep", dummy_sleep):
         
        stream = generate_lesson_stream("session-123", "Tema: Multiplicacion")
        chunks = []
        async for chunk in stream:
            chunks.append(json.loads(chunk))
            
        assert any(c["status"] == "error" for c in chunks)
        error_chunk = next(c for c in chunks if c["status"] == "error")
        assert "Gemini Down" in error_chunk["message"]

@pytest.mark.asyncio
async def test_generate_lesson_stream_exception_fase2():
    mock_client = MagicMock()
    
    mock_response_core = MagicMock()
    mock_response_core.text = '{"tema": "Multiplicacion"}'
    
    mock_client.models.generate_content.side_effect = [
        mock_response_core,
        Exception("Gemini Down Fase 2")
    ]
    
    with patch("services.client", mock_client), \
         patch("services.save_session_input", MagicMock()), \
         patch("services.update_session_status", MagicMock()), \
         patch("asyncio.sleep", dummy_sleep):
         
        stream = generate_lesson_stream("session-123", "Tema: Multiplicacion")
        chunks = []
        async for chunk in stream:
            chunks.append(json.loads(chunk))
            
        assert any(c["status"] == "error" for c in chunks)
        error_chunk = next(c for c in chunks if c["status"] == "error")
        assert "Gemini Down Fase 2" in error_chunk["message"]

@pytest.mark.asyncio
async def test_generate_lesson_stream_exception_json():
    mock_client = MagicMock()
    
    mock_response_core = MagicMock()
    mock_response_core.text = 'invalid-json'
    
    mock_client.models.generate_content.return_value = mock_response_core
    
    with patch("services.client", mock_client), \
         patch("services.save_session_input", MagicMock()), \
         patch("services.update_session_status", MagicMock()), \
         patch("asyncio.sleep", dummy_sleep):
         
        stream = generate_lesson_stream("session-123", "Tema: Multiplicacion")
        chunks = []
        async for chunk in stream:
            chunks.append(json.loads(chunk))
            
        assert any(c["status"] == "error" for c in chunks)

@pytest.mark.asyncio
async def test_generate_lesson_result_success():
    async def mock_stream(sid, msg):
        yield json.dumps({"status": "progress", "step": "Working"})
        yield json.dumps({"status": "completed", "data": {"res": "ok"}})
        
    with patch("services.generate_lesson_stream", mock_stream):
        res = await generate_lesson_result("session-123", "hello")
        assert res == {"res": "ok"}

@pytest.mark.asyncio
async def test_generate_lesson_result_error():
    async def mock_stream(sid, msg):
        yield json.dumps({"status": "progress", "step": "Working"})
        yield json.dumps({"status": "error", "message": "Failed"})
        
    with patch("services.generate_lesson_stream", mock_stream):
        res = await generate_lesson_result("session-123", "hello")
        assert res == {"error": "Failed"}
