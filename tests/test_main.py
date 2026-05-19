import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app
from database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_startup_event():
    with patch("main.init_db") as mock_init_db, \
         patch("main.init_knowledge_base") as mock_init_kb:
        with TestClient(app) as tc:
            res = tc.get("/")
            assert res.status_code == 200
        mock_init_db.assert_called_once()
        mock_init_kb.assert_called_once()

def test_home():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_create_session():
    payload = {"session_id": "test-123", "data": {"tema": "Fracciones"}}
    res = client.post("/api/sessions", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "test-123"
    assert data["input_data"]["tema"] == "Fracciones"

def test_create_session_empty():
    res = client.post("/api/sessions", json={})
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data

def test_create_session_form_data():
    payload = {"session_id": "test-form-123", "tema": "Fracciones"}
    res = client.post("/api/sessions", data=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "test-form-123"

def test_read_request_payload_invalid_json():
    res = client.post("/api/sessions", content="invalid{json", headers={"Content-Type": "application/json"})
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data

def test_read_request_payload_form_fail():
    with patch("fastapi.Request.form", side_effect=Exception("form fail")):
        res = client.post("/api/sessions", data={"key": "val"})
        assert res.status_code == 200

def test_get_all_sessions():
    client.post("/api/sessions", json={"session_id": "s1", "data": {"tema": "Fracciones"}})
    res = client.get("/api/sessions")
    assert res.status_code == 200
    assert len(res.json()) >= 1

def test_save_session_endpoint():
    payload = {
        "user_id": "user123",
        "session_data": {
            "id": "s1",
            "tema": "Calculo"
        }
    }
    res = client.post("/api/sessions/save", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_like_session_not_found():
    res = client.post("/api/sessions/s-nonexistent/like")
    assert res.status_code == 404

def test_like_session_success():
    # Save a generated session first
    from database import save_generated_session
    save_generated_session("s1", {"tema": "Math", "likes": 0})
    res = client.post("/api/sessions/s1/like")
    assert res.status_code == 200
    assert res.json()["likes"] == 1

def test_comment_session_empty():
    res = client.post("/api/sessions/s1/comment", json={"text": ""})
    assert res.status_code == 400

def test_comment_session_not_found():
    res = client.post("/api/sessions/s-nonexistent/comment", json={"text": "bueno"})
    assert res.status_code == 404

def test_comment_session_success():
    from database import save_generated_session
    save_generated_session("s1", {"tema": "Math", "comments": []})
    res = client.post("/api/sessions/s1/comment", json={"author": "Juan", "text": "Buenisimo"})
    assert res.status_code == 200
    assert res.json()["comment"]["author"] == "Juan"

def test_get_session_detail_not_found():
    res = client.get("/api/sessions/s-nonexistent")
    assert res.status_code == 404

def test_get_session_detail_success():
    from database import save_session_input
    save_session_input("s1", {"tema": "Calculo"})
    res = client.get("/api/sessions/s1")
    assert res.status_code == 200
    assert res.json()["session_id"] == "s1"

def test_receive_session_form():
    res = client.post("/api/sessions/s1/form", json={"tema": "Algebra"})
    assert res.status_code == 200
    assert res.json()["input_data"]["tema"] == "Algebra"

def test_generate_session_no_data():
    res = client.post("/api/sessions/s-empty/generate", json={})
    assert res.status_code == 400

def test_generate_session_success():
    from database import save_session_input
    save_session_input("s1", {"tema": "Calculo"})
    with patch("main.generate_lesson_result", return_value={"tema": "Calculo"}) as mock_gen:
        res = client.post("/api/sessions/s1/generate", json={})
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

def test_generate_session_with_data():
    with patch("main.generate_lesson_result", return_value={"tema": "Algebra"}) as mock_gen:
        res = client.post("/api/sessions/s1/generate", json={"tema": "Algebra"})
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

def test_generate_session_error():
    from database import save_session_input
    save_session_input("s1", {"tema": "Calculo"})
    with patch("main.generate_lesson_result", return_value={"error": "API Limit"}) as mock_gen:
        res = client.post("/api/sessions/s1/generate", json={})
        assert res.status_code == 500

def test_download_session_not_found():
    res = client.get("/api/sessions/s-nonexistent/download")
    assert res.status_code == 404

def test_download_session_success():
    from database import save_generated_session
    save_generated_session("s1", {"tema": "Math"})
    res = client.get("/api/sessions/s1/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json; charset=utf-8"

def test_generate_stream():
    async def mock_stream(sid, msg):
        yield "chunk1"
        yield "chunk2"
        
    with patch("main.generate_lesson_stream", mock_stream):
        res = client.get("/api/generate-stream?session_id=s1&message=hello")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

def test_websocket_generate():
    async def mock_stream(sid, msg):
        yield "chunk1"
        yield "chunk2"
        
    with patch("main.generate_lesson_stream", mock_stream):
        with client.websocket_connect("/ws/generate") as websocket:
            websocket.send_text('{"session_id": "s1", "message": "hello"}')
            data1 = websocket.receive_text()
            data2 = websocket.receive_text()
            assert data1 == "chunk1"
            assert data2 == "chunk2"

def test_websocket_generate_exception():
    with patch("main.generate_lesson_stream", side_effect=Exception("WS failure")):
        with client.websocket_connect("/ws/generate") as websocket:
            websocket.send_text('{"session_id": "s1", "message": "hello"}')
            data = websocket.receive_text()
            assert "WS failure" in data
