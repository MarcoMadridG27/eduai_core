import re
import json


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

            for k, v in payload.items():
                k_low = str(k).strip().lower()
                mapped = key_map.get(k_low)
                if mapped:
                    out[mapped] = str(v).strip()

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
    if not any(v for v in normalized.values() if v and v != "2 horas"):
        normalized["titulo"] = message.strip()

    return normalized

