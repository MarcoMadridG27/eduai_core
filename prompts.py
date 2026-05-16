# ========================
# Construcción de prompts (Fase 1 y 2)
# ========================

def build_core_prompt(inputs, retrieved_docs):
    """
    Construye el prompt para la primera fase: Plan Base de la sesión.
    """
    prompt = (
        "Requisitos de la sesión:\n"
        "- Usa lenguaje claro y profesional dirigido a docentes peruanos.\n"
        "- RESPETA ESTRICTAMENTE la duración especificada (1 hora pedagógica = 45 minutos).\n"
        "- Adecúa la dificultad y las estrategias pedagógicas al grado o ciclo indicado.\n"
        "- CONTEXTUALIZACIÓN OBLIGATORIA: TODAS las actividades deben relacionarse con el contexto sociocultural indicado.\n"
        "- La distribución del tiempo debe ser realista (Inicio: 15-20%, Desarrollo: 60-70%, Cierre: 10-15%).\n"
        "- Secuencia Metodológica Detallada:\n"
        "  * INICIO: motivación contextualizada, problematización, saberes previos, propósito\n"
        "  * DESARROLLO: situación problemática + 5 procesos didácticos de Matemática + trabajo variado\n"
        "  * CIERRE: metacognición, transferencia, evaluación formativa\n"
        "- Procesos Didácticos de Matemática (siempre en este orden): "
        "1. Familiarización con el problema, 2. Búsqueda y ejecución de estrategias, "
        "3. Socialización de representaciones, 4. Reflexión y formalización, 5. Planteamiento de otros problemas.\n\n"
    )

    prompt += (
        "**DATOS GENERALES Y CONTEXTO:**\n"
        f"- Título: {inputs.get('titulo', '')}\n"
        f"- Docente: {inputs.get('docente', '')}\n"
        f"- Fecha: {inputs.get('fecha', '')}\n"
        f"- Grado/Sección/Ciclo: {inputs.get('grado', '')} {inputs.get('seccion', '')} ({inputs.get('ciclo', '')})\n"
        f"- Competencias y Capacidades: {inputs.get('competencias', '')} / {inputs.get('capacidades', '')}\n"
        f"- Contexto sociocultural: {inputs.get('contexto', '')}\n"
        f"- Duración: {inputs.get('duracion', '')} (Ajusta los tiempos a esto)\n"
        f"- Enfoques Transversales: {inputs.get('enfoque_transversal', '')} / {inputs.get('competencia_transversal', '')}\n"
        f"- Materiales disponibles: {inputs.get('materiales', '')}\n\n"
    )

    if retrieved_docs:
        prompt += "Fragmentos relevantes del Currículo Nacional:\n"
        for i, doc in enumerate(retrieved_docs, 1):
            prompt += f"{i}. {doc.strip()}\n"
        prompt += "\n"

    prompt += "Genera el Plan Base de la sesión estructurada."
    return prompt


def build_resources_prompt(core_plan_json):
    """
    Construye el prompt para la segunda fase: Generación de recursos complementarios.
    """
    prompt = (
        "Basado estrictamente en el siguiente Plan de Sesión de Aprendizaje, genera los Recursos Adicionales solicitados "
        "para complementar la clase. Asegúrate de que las actividades estén conectadas con el propósito y el contexto.\n\n"
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
