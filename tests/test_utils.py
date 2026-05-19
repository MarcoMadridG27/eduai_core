import pytest
from utils import (
    _split_multi_value,
    parse_duration_hours,
    format_duration_text,
    parse_teacher_message,
    normalize_session_input
)

def test_split_multi_value():
    assert _split_multi_value(None) == []
    assert _split_multi_value(["a", "b"]) == ["a", "b"]
    assert _split_multi_value("a, b, c") == ["a", "b", "c"]
    assert _split_multi_value("  ") == []

def test_parse_duration_hours():
    assert parse_duration_hours(None) == 2
    assert parse_duration_hours("") == 2
    assert parse_duration_hours(5) == 5
    assert parse_duration_hours("3 horas") == 3
    assert parse_duration_hours("no numbers") == 2

def test_format_duration_text():
    assert format_duration_text(None) == "2 horas"
    assert format_duration_text(1) == "1 hora"
    assert format_duration_text(3) == "3 horas"

def test_parse_teacher_message_empty():
    empty_res = parse_teacher_message("")
    assert empty_res["titulo"] == ""
    assert empty_res["horasClase"] == 2

def test_parse_teacher_message_json():
    json_msg = '{"titulo": "Matematicas", "duracion": "4 horas", "grado": "5to"}'
    res = parse_teacher_message(json_msg)
    assert res["titulo"] == "Matematicas"
    assert res["grado"] == "5to"
    assert res["horasClase"] == 4

def test_parse_teacher_message_text_labels():
    text_msg = "Titulo: Fracciones\nDocente: Juan Perez\nGrado: 3ero\nDuracion: 3 horas"
    res = parse_teacher_message(text_msg)
    assert res["titulo"] == "Fracciones"
    assert res["docente"] == "Juan Perez"
    assert res["grado"] == "3ero"
    assert res["horasClase"] == 3

def test_parse_teacher_message_free_text():
    res = parse_teacher_message("Solo un titulo de clase libre")
    assert res["titulo"] == "Solo un titulo de clase libre"

def test_normalize_session_input_none():
    res = normalize_session_input(None)
    assert res["titulo"] == ""

def test_normalize_session_input_string():
    res = normalize_session_input("Titulo: Algebra\nDuracion: 4 horas")
    assert res["titulo"] == "Algebra"
    assert res["horasClase"] == 4

def test_normalize_session_input_dict():
    payload = {
        "tema": "Geometria",
        "competencias": ["Competencia 1"],
        "capacidades": ["Capacidad 1"],
        "materiales": ["Pizarra"],
        "horasClase": 3
    }
    res = normalize_session_input(payload)
    assert res["titulo"] == "Geometria"
    assert res["competenciasSeleccionadas"] == ["Competencia 1"]
    assert res["capacidades"] == ["Capacidad 1"]
    assert res["horasClase"] == 3

def test_normalize_session_input_non_dict():
    res = normalize_session_input([("tema", "Ecuaciones")])
    assert res["titulo"] == "Ecuaciones"
