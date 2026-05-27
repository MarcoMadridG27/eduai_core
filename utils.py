import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_DURATION_TEXT = "2 horas"



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
            "duracion": DEFAULT_DURATION_TEXT,
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
                "idioma": "idioma",
                "language": "idioma",
            }

            out = dict.fromkeys(key_map.values(), "")
            out["duracion"] = DEFAULT_DURATION_TEXT
            out["horasClase"] = 2
            out["idioma"] = "español"

            for k, v in payload.items():
                k_low = str(k).strip().lower()
                mapped = key_map.get(k_low)
                if mapped:
                    out[mapped] = str(v).strip()

            out["tema"] = out.get("titulo", "")
            out["horasClase"] = parse_duration_hours(
                out.get("duracion"), default=2)

            return out
    except Exception:
        pass

    # 2) Texto con etiquetas: extraer bloques multilínea entre etiquetas
    labels = [
        "Tema de la Sesión", "Tema", "Título", "Titulo", "Docente", "Fecha", "Grado", "Sección", "Seccion",
        "Competencias", "Capacidades", "Enfoque Transversal", "Competencia Transversal", "Ciclo", 
        "Contexto Social", "Contexto", "Duración", "Duracion", "Materiales", "Idioma", "Language",
        "Instrumento de Evaluación Sugerido"
    ]

    # Construir patrón que capture label y su contenido hasta la siguiente etiqueta o EOF
    labels_pattern = "|".join(re.escape(lbl) for lbl in labels)
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
        "duracion": DEFAULT_DURATION_TEXT,
        "enfoque_transversal": "",
        "competencia_transversal": "",
        "materiales": "",
        "horasClase": 2,
        "idioma": "español",
    }

    label_map = {
        "tema de la sesión": "tema", "tema": "tema",
        "título": "titulo", "titulo": "titulo",
        "docente": "docente",
        "fecha": "fecha",
        "grado": "grado",
        "sección": "seccion", "seccion": "seccion",
        "competencias": "competencias",
        "capacidades": "capacidades",
        "ciclo": "ciclo",
        "contexto social": "contexto", "contexto": "contexto",
        "duración": "duracion", "duracion": "duracion",
        "enfoque transversal": "enfoque_transversal",
        "competencia transversal": "competencia_transversal",
        "materiales": "materiales",
        "idioma": "idioma",
        "language": "idioma",
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
    normalized["horasClase"] = parse_duration_hours(
        normalized.get("duracion"), default=2)

    return normalized


def format_date_peru(value):
    """Convierte varias representaciones de fecha a formato DD/MM/YYYY (Perú).

    Acepta formatos comunes: ISO YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, DD/MM/YYYY, etc.
    Si no puede parsear, intenta extraer con regex. Devuelve cadena vacía si no hay valor.
    """
    if not value:
        return ""
    if isinstance(value, datetime):
        # Ensure datetime is represented in PET (America/Lima, UTC-5)
        try:
            lima = ZoneInfo("America/Lima")
            if value.tzinfo is None:
                # assume UTC for naive datetimes
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(lima)
            return value.strftime("%d/%m/%Y")
        except Exception:
            return value.strftime("%d/%m/%Y")
    s = str(value).strip()
    if not s:
        return ""
    # Manejar ISO con Z
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        lima = ZoneInfo("America/Lima")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(lima)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        pass
    # Intents with common formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            continue
    # Fallback regex
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m2 = re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m2:
        return s
    return s


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
            "fecha": format_date_peru(parsed.get("fecha", "")),
            "grado": parsed.get("grado", ""),
            "seccion": parsed.get("seccion", ""),
            "competenciasSeleccionadas": _split_multi_value(parsed.get("competencias", "")),
            "capacidades": _split_multi_value(parsed.get("capacidades", "")),
            "ciclo": parsed.get("ciclo", ""),
            "contexto": parsed.get("contexto", ""),
            "duracion": format_duration_text(parsed.get("duracion", DEFAULT_DURATION_TEXT)),
            "horasClase": parse_duration_hours(parsed.get("horasClase") or parsed.get("duracion"), default=2),
            "enfoqueTransversal": parsed.get("enfoque_transversal", ""),
            "competenciaTransversal": parsed.get("competencia_transversal", ""),
            "materialesDisponibles": parsed.get("materiales", ""),
            "idioma": parsed.get("idioma", "español").split("\n")[0].strip(),
        }

    if not isinstance(payload, dict):
        payload = dict(payload)

    tema = payload.get("tema") or payload.get(
        "titulo") or payload.get("title") or ""
    competencias = payload.get(
        "competenciasSeleccionadas") or payload.get("competencias") or []
    capacidades = payload.get("capacidades") or payload.get(
        "capacidadesSeleccionadas") or []
    materiales = payload.get(
        "materialesDisponibles") or payload.get("materiales") or []
    duracion = payload.get("duracion") or payload.get(
        "horasClase") or DEFAULT_DURATION_TEXT
    horas_clase = parse_duration_hours(
        payload.get("horasClase") or duracion, default=2)

    return {
        "tema": str(tema).strip(),
        "titulo": str(tema).strip(),
        "docente": str(payload.get("docente", "")).strip(),
        "fecha": format_date_peru(str(payload.get("fecha", "")).strip()),
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
        "idioma": str(payload.get("idioma") or payload.get("language") or "español").split("\n")[0].strip(),
        "rawInput": payload,
    }
