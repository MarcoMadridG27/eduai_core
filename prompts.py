# ========================
# Construcción de prompts (Fase 1 y 2)
# ========================


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def build_core_prompt(inputs, retrieved_docs):
    """Construye el prompt para la primera fase con el contrato JSON esperado."""
    tema = _as_text(inputs.get("tema") or inputs.get("titulo"))
    ciclo = _as_text(inputs.get("ciclo"))
    contexto = _as_text(inputs.get("contexto"))
    horas_clase = inputs.get("horasClase") or inputs.get("horas_clase") or 2
    competencias = _as_text(inputs.get(
        "competenciasSeleccionadas") or inputs.get("competencias"))
    capacidades = _as_text(inputs.get("capacidades"))
    materiales = _as_text(inputs.get("materialesDisponibles")
                          or inputs.get("materiales"))
    docente = _as_text(inputs.get("docente"))
    fecha = _as_text(inputs.get("fecha"))
    grado = _as_text(inputs.get("grado"))
    seccion = _as_text(inputs.get("seccion"))
    enfoque_transversal = _as_text(inputs.get(
        "enfoqueTransversal") or inputs.get("enfoque_transversal"))
    competencia_transversal = _as_text(inputs.get(
        "competenciaTransversal") or inputs.get("competencia_transversal"))
    idioma = _as_text(inputs.get("idioma") or "español")

    prompt = (
        "Eres un asistente pedagógico experto en Matemática del Currículo Nacional Peruano del MINEDU. "
        "Debes devolver SOLO un JSON válido, sin markdown ni texto adicional.\n\n"
        "Requisitos obligatorios:\n"
        f"- Idioma obligatorio de redacción de todo el contenido textual (secuencia didáctica, criterios de evaluación, propósito de sesión, etc.): {idioma}. Todo el texto generado por la IA DEBE estar redactado íntegramente en {idioma}.\n"
        f"- Claves del JSON de salida: Las claves del objeto JSON resultante (ej. 'tema', 'ciclo', 'secuenciaMetodologica', 'inicio', 'desarrollo', 'cierre', etc.) DEBEN permanecer exactamente en español, idénticas al contrato de salida. ÚNICAMENTE traduce el contenido textual de los valores.\n"
        "- Coherencia pedagógica entre competencias, capacidades, propósito, evaluación y actividades.\n"
        "- Contextualización real al entorno indicado.\n"
        "- Usa la cantidad de horas clase indicada y distribúyelas de forma realista.\n"
        "- Respeta el siguiente orden en procesos didácticos: Familiarización con el problema, Búsqueda y ejecución de estrategias, Socialización de representaciones, Reflexión y formalización, Planteamiento de otros problemas.\n\n"
        "Contrato de salida esperado:\n"
        "{\n"
        '  "tema": "string",\n'
        '  "ciclo": "string",\n'
        '  "contexto": "string",\n'
        '  "horasClase": number,\n'
        '  "competenciasSeleccionadas": ["string"],\n'
        '  "capacidades": ["string"],\n'
        '  "materialesDisponibles": "string",\n'
        '  "actividades_previas": ["string"],\n'
        '  "competenciaDescripcion": "string",\n'
        '  "desempenos": ["string"],\n'
        '  "criteriosEvaluacion": "string",\n'
        '  "evidenciasAprendizaje": "string",\n'
        '  "propositoSesion": "string",\n'
        '  "secuenciaMetodologica": { "inicio": "string", "desarrollo": "string", "cierre": "string" },\n'
        '  "distribucionHoras": "string",\n'
        '  "procesosDidacticos": ["string"],\n'
        '  "actividadesContextualizadas": ["string"],\n'
        '  "materialesDidacticosSugeridos": ["string"],\n'
        '  "actitudes_observables": "string"\n'
        "}\n\n"
        "Datos de entrada:\n"
        f"- Tema: {tema}\n"
        f"- Docente: {docente}\n"
        f"- Fecha: {fecha}\n"
        f"- Grado: {grado}\n"
        f"- Sección: {seccion}\n"
        f"- Ciclo: {ciclo}\n"
        f"- Contexto sociocultural: {contexto}\n"
        f"- Horas clase: {horas_clase}\n"
        f"- Competencias seleccionadas: {competencias}\n"
        f"- Capacidades: {capacidades}\n"
        f"- Materiales disponibles: {materiales}\n"
        f"- Enfoque transversal: {enfoque_transversal}\n"
        f"- Competencia transversal: {competencia_transversal}\n\n"
        "Fragmentos relevantes del Currículo Nacional:\n"
    )

    if retrieved_docs:
        for i, doc in enumerate(retrieved_docs, 1):
            prompt += f"{i}. {doc.strip()}\n"
    else:
        prompt += "- No se recuperaron fragmentos adicionales.\n"

    prompt += (
        "\nGenera una sesión completa, pedagógicamente sólida y realista. "
        "Asegúrate de que `horasClase` sea numérico y que las listas sean arrays JSON válidos. "
        "Incluye `actividades_previas` como una lista breve y concreta de acciones antes de la sesión. "
        "No la dejes vacía: si no hay instrucciones explícitas, infiere 3 a 5 acciones previas a partir del contexto, "
        "las competencias, las capacidades y los materiales disponibles. "
        "Incluye `desempenos` como una lista breve de desempeños por grado coherentes con la competencia y capacidades. "
        "Incluye `actitudes_observables` como una descripción breve y concreta de actitudes o acciones observables alineadas al enfoque transversal."
    )
    return prompt


def build_resources_prompt(core_plan_json, idioma="español"):
    """
    Construye el prompt para la segunda fase: Generación de recursos complementarios.
    """
    prompt = (
        "Basado estrictamente en el siguiente Plan de Sesión de Aprendizaje, genera los Recursos Adicionales solicitados "
        "para complementar la clase. Asegúrate de que las actividades estén conectadas con el propósito y el contexto.\n\n"
        "Requisitos obligatorios:\n"
        f"- Idioma obligatorio de redacción de todo el contenido textual (instrucciones, enunciados, comunicados, etc.): {idioma}. Todo el texto generado por la IA DEBE estar redactado íntegramente en {idioma}.\n"
        f"- Claves del JSON de salida: Las claves del objeto JSON resultante (ej. 'fichasDeTrabajo', 'problemasYEjercicios', 'juegoDidactico', 'comunicadoParaPadres', etc.) DEBEN permanecer exactamente en español, idénticas al esquema esperado. ÚNICAMENTE traduce el contenido de los valores.\n\n"
        f"PLAN DE SESIÓN:\n{core_plan_json}\n\n"
        "Debes generar:\n"
        "1. Fichas de trabajo con niveles progresivos.\n"
        "2. Problemas y ejercicios para resolver.\n"
        "3. Un juego didáctico acorde a los materiales disponibles.\n"
        "4. Actividades de activación cortas (Inicio).\n"
        "5. Evaluación formativa con respuestas correctas.\n"
        "6. Un comunicado amigable para padres (apropiado para WhatsApp).\n"
        "7. Actividades diferenciadas (Refuerzo, Consolidación, Profundización).\n"
    )
    return prompt
