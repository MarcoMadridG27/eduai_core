import re
import json

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
# clean_model_output function removed because it's not referenced
# def clean_model_output(raw: str):
#     # (commented) Implemented JSON cleaning for model outputs.
#     pass
