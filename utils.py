import re
import json


def _split_multi_value(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [part.strip() for part in str(value).split(",")]
    return [item.strip() for item in items if str(item).strip()]


def parse_duration_hours(value, default=2):
    """Extrae la cantidad de horas pedagógicas desde texto o número."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else default


def format_duration_text(value, default=2):
    hours = parse_duration_hours(value, default=default)
    return f"{hours} hora{'s' if hours != 1 else ''}"


def parse_teacher_message(message: str):
    """Parsea la entrada del docente.

    Soporta tres formatos comunes:
    - JSON válido (devuelve la carga mapeada a las claves esperadas)
    - Texto con campos etiquetados (ej. "Título: ...\nDocente: ..."), admite valores multilínea
    - Texto libre: si no se detectan etiquetas ni JSON, usa todo el texto como `titulo`.

    Devuelve un dict con las claves esperadas por el resto de la aplicación.
    """
    if not message:
        return {
            "tema": "",
            "titulo": "",
            "docente": "",
            "fecha": "",
            "grado": "",
            "seccion": "",
            "competencias": "",
            "capacidades": "",
            "ciclo": "",
            "contexto": "",
            "duracion": "2 horas",
            "enfoque_transversal": "",
            "competencia_transversal": "",
            "materiales": "",
            "horasClase": 2,
        }

    # 1) Intentar JSON
    try:
        payload = json.loads(message)
        if isinstance(payload, dict):
            # Normalizar claves (acepta variantes en español/without accents)
            key_map = {
                "título": "titulo",
                "titulo": "titulo",
                "title": "titulo",
                "docente": "docente",
                "teacher": "docente",
                "fecha": "fecha",
                "date": "fecha",
                "grado": "grado",
                "grade": "grado",
                "sección": "seccion",
                "seccion": "seccion",
                "competencias": "competencias",
                "capacidades": "capacidades",
                "ciclo": "ciclo",
                "contexto": "contexto",
                "duración": "duracion",
                "duracion": "duracion",
                "enfoque_transversal": "enfoque_transversal",
                "enfoque transversal": "enfoque_transversal",
                "competencia_transversal": "competencia_transversal",
                "competencia transversal": "competencia_transversal",
                "materiales": "materiales",
                "materials": "materiales",
            }

            out = {v: "" for v in key_map.values()}
            out["duracion"] = "2 horas"
            out["horasClase"] = 2

            for k, v in payload.items():
                k_low = str(k).strip().lower()
                mapped = key_map.get(k_low)
                if mapped:
                    out[mapped] = str(v).strip()

            out["tema"] = out.get("titulo", "")
            out["horasClase"] = parse_duration_hours(out.get("duracion"), default=2)

            return out
    except Exception:
        pass

    # 2) Texto con etiquetas: extraer bloques multilínea entre etiquetas
    labels = [
        "Título", "Titulo", "Docente", "Fecha", "Grado", "Sección", "Seccion",
        "Competencias", "Capacidades", "Ciclo", "Contexto", "Duración", "Duracion",
        "Enfoque Transversal", "Competencia Transversal", "Materiales"
    ]

    # Construir patrón que capture label y su contenido hasta la siguiente etiqueta o EOF
    labels_pattern = "|".join(re.escape(l) for l in labels)
    pattern = re.compile(
        rf"(?ms)^\s*(?P<label>{labels_pattern})\s*:\s*(?P<value>.*?)(?=^\s*(?:{labels_pattern})\s*:|\Z)",
        re.IGNORECASE,
    )

    matches = list(pattern.finditer(message))
    normalized = {
        "tema": "",
        "titulo": "",
        "docente": "",
        "fecha": "",
        "grado": "",
        "seccion": "",
        "competencias": "",
        "capacidades": "",
        "ciclo": "",
        "contexto": "",
        "duracion": "2 horas",
        "enfoque_transversal": "",
        "competencia_transversal": "",
        "materiales": "",
        "horasClase": 2,
    }

    label_map = {
        "título": "titulo", "titulo": "titulo",
        "docente": "docente",
        "fecha": "fecha",
        "grado": "grado",
        "sección": "seccion", "seccion": "seccion",
        "competencias": "competencias",
        "capacidades": "capacidades",
        "ciclo": "ciclo",
        "contexto": "contexto",
        "duración": "duracion", "duracion": "duracion",
        "enfoque transversal": "enfoque_transversal",
        "competencia transversal": "competencia_transversal",
        "materiales": "materiales",
    }

    for m in matches:
        label = m.group("label").strip().lower()
        value = m.group("value").strip()
        mapped = label_map.get(label)
        if mapped:
            normalized[mapped] = value

    # 3) Si no encontramos nada, usar todo el texto como título
    if not normalized.get("titulo") and not normalized.get("docente") and not normalized.get("contexto") and not normalized.get("competencias"):
        normalized["titulo"] = message.strip()

    normalized["tema"] = normalized.get("titulo", "")
    normalized["horasClase"] = parse_duration_hours(normalized.get("duracion"), default=2)

    return normalized


def normalize_session_input(payload):
    """Normaliza payloads de frontend, JSON o texto libre al contrato interno."""
    if payload is None:
        payload = {}

    if isinstance(payload, str):
        parsed = parse_teacher_message(payload)
        return {
            "tema": parsed.get("tema") or parsed.get("titulo", ""),
            "titulo": parsed.get("tema") or parsed.get("titulo", ""),
            "docente": parsed.get("docente", ""),
            "fecha": parsed.get("fecha", ""),
            "grado": parsed.get("grado", ""),
            "seccion": parsed.get("seccion", ""),
            "competenciasSeleccionadas": _split_multi_value(parsed.get("competencias", "")),
            "capacidades": _split_multi_value(parsed.get("capacidades", "")),
            "ciclo": parsed.get("ciclo", ""),
            "contexto": parsed.get("contexto", ""),
            "duracion": format_duration_text(parsed.get("duracion", "2 horas")),
            "horasClase": parse_duration_hours(parsed.get("horasClase") or parsed.get("duracion"), default=2),
            "enfoqueTransversal": parsed.get("enfoque_transversal", ""),
            "competenciaTransversal": parsed.get("competencia_transversal", ""),
            "materialesDisponibles": parsed.get("materiales", ""),
        }

    if not isinstance(payload, dict):
        payload = dict(payload)

    tema = payload.get("tema") or payload.get("titulo") or payload.get("title") or ""
    competencias = payload.get("competenciasSeleccionadas") or payload.get("competencias") or []
    capacidades = payload.get("capacidades") or payload.get("capacidadesSeleccionadas") or []
    materiales = payload.get("materialesDisponibles") or payload.get("materiales") or []
    duracion = payload.get("duracion") or payload.get("horasClase") or "2 horas"
    horas_clase = parse_duration_hours(payload.get("horasClase") or duracion, default=2)

    return {
        "tema": str(tema).strip(),
        "titulo": str(tema).strip(),
        "docente": str(payload.get("docente", "")).strip(),
        "fecha": str(payload.get("fecha", "")).strip(),
        "grado": str(payload.get("grado", "")).strip(),
        "seccion": str(payload.get("seccion", "")).strip(),
        "competenciasSeleccionadas": _split_multi_value(competencias),
        "capacidades": _split_multi_value(capacidades),
        "ciclo": str(payload.get("ciclo", "")).strip(),
        "contexto": str(payload.get("contexto", "")).strip(),
        "duracion": format_duration_text(duracion, default=horas_clase),
        "horasClase": horas_clase,
        "enfoqueTransversal": str(payload.get("enfoqueTransversal") or payload.get("enfoque_transversal") or "").strip(),
        "competenciaTransversal": str(payload.get("competenciaTransversal") or payload.get("competencia_transversal") or "").strip(),
        "materialesDisponibles": ", ".join(_split_multi_value(materiales)),
        "materialesLista": _split_multi_value(materiales),
        "rawInput": payload,
    }

