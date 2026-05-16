import re
import json

# ========================
# Funciones de utilidad
# ========================
def parse_teacher_message(message: str):
    """Extrae los campos enviados por el frontend como texto plano."""
    titulo = re.search(r"Título:\s*(.*)", message)
    docente = re.search(r"Docente:\s*(.*)", message)
    fecha = re.search(r"Fecha:\s*(.*)", message)
    grado = re.search(r"Grado:\s*(.*)", message)
    seccion = re.search(r"Sección:\s*(.*)", message)
    competencias = re.search(r"Competencias:\s*(.*)", message)
    capacidades = re.search(r"Capacidades:\s*(.*)", message)
    ciclo = re.search(r"Ciclo:\s*(.*)", message)
    contexto = re.search(r"Contexto:\s*(.*)", message)
    duracion = re.search(r"Duración:\s*(.*)", message)
    enfoque_transversal = re.search(r"Enfoque Transversal:\s*(.*)", message)
    competencia_transversal = re.search(r"Competencia Transversal:\s*(.*)", message)
    materiales = re.search(r"Materiales:\s*(.*)", message)

    return {
        "titulo": titulo.group(1).strip() if titulo else "",
        "docente": docente.group(1).strip() if docente else "",
        "fecha": fecha.group(1).strip() if fecha else "",
        "grado": grado.group(1).strip() if grado else "",
        "seccion": seccion.group(1).strip() if seccion else "",
        "competencias": competencias.group(1).strip() if competencias else "",
        "capacidades": capacidades.group(1).strip() if capacidades else "",
        "ciclo": ciclo.group(1).strip() if ciclo else "",
        "contexto": contexto.group(1).strip() if contexto else "",
        "duracion": duracion.group(1).strip() if duracion else "2 horas",
        "enfoque_transversal": enfoque_transversal.group(1).strip() if enfoque_transversal else "",
        "competencia_transversal": competencia_transversal.group(1).strip() if competencia_transversal else "",
        "materiales": materiales.group(1).strip() if materiales else "",
    }

def clean_model_output(raw: str):
    """Intenta limpiar outputs de modelos que vienen como texto con code-fences
    o texto extra y devuelve (obj, cleaned_string).
    - Si puede parsear JSON devuelve el objeto y la cadena usada.
    - Si no puede, devuelve (None, cleaned_candidate).
    """
    if not isinstance(raw, str):
        return None, None

    s = raw.strip()

    # Remover code fences como ```json ... ``` o ``` ... ```
    m = re.match(r"^```(?:json)?\s*([\s\S]*)\s*```$", s, re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    # A veces vienen con comillas extra o texto antes/ despues; buscar primer '{' y último '}'
    first = s.find('{')
    last = s.rfind('}')
    if first != -1 and last != -1 and last > first:
        candidate = s[first:last+1]
    else:
        candidate = s

    # Intentar cargar JSON directamente
    try:
        obj = json.loads(candidate)
        return obj, candidate
    except Exception:
        # Intentar otras limpiezas comunes
        candidate2 = candidate.strip().strip('"')
        candidate2 = candidate2.replace('\n', '\\n')
        try:
            obj = json.loads(candidate2)
            return obj, candidate2
        except Exception:
            # No se pudo parsear
            return None, candidate
