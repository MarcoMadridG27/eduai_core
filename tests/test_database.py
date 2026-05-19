import pytest
from database import (
    init_db,
    save_message,
    save_session_input,
    save_generated_session,
    update_session_status,
    get_all_sessions_db,
    get_session
)

def test_database_flow():
    # Initialize DB (autouse fixture already does it but let's test it)
    init_db()
    
    session_id = "test-session-123"
    
    # Test saving session input
    input_data = {"tema": "Ecuaciones", "grado": "4to"}
    save_session_input(session_id, input_data, source="test", status="draft")
    
    session = get_session(session_id)
    assert session is not None
    assert session["session_id"] == session_id
    assert session["source"] == "test"
    assert session["status"] == "draft"
    assert session["input_data"] == input_data
    assert session["generated_data"] is None
    
    # Test updating session status
    update_session_status(session_id, "generating", source="test")
    session = get_session(session_id)
    assert session["status"] == "generating"
    
    # Test saving generated session
    gen_data = {"result": "ok"}
    save_generated_session(session_id, gen_data, source="test", status="completed")
    session = get_session(session_id)
    assert session["status"] == "completed"
    assert session["generated_data"] == gen_data
    
    # Test saving message history
    save_message(session_id, "user", "Hola")
    save_message(session_id, "bot", "Mundo")
    
    # Test getting all sessions
    all_sessions = get_all_sessions_db()
    assert len(all_sessions) >= 1
    assert any(s["session_id"] == session_id for s in all_sessions)

def test_get_nonexistent_session():
    assert get_session("nonexistent-id") is None
