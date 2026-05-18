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
        f"- Materiales disponibles: {inputs.get('materiales', '')}\n"
    )

    instrumento = inputs.get('instrumento_evaluacion', '').strip()
    if instrumento and instrumento != "A decisión de la IA":
        prompt += f"- Instrumento de Evaluación Sugerido: {instrumento}\n"
        if "Rúbrica" in instrumento:
            prompt += "  * Genera criterios de evaluación con 3 niveles de logro: Logrado / En proceso / En inicio.\n"
            prompt += "  * La evidencia de aprendizaje debe ser un producto evaluable con esos niveles.\n"
            prompt += "  * En el CIERRE de la secuencia metodológica incluye explícitamente: 'El docente aplica la rúbrica mientras...'\n"
        elif "Lista de cotejo" in instrumento:
            prompt += "  * Genera criterios de evaluación como afirmaciones observables (SÍ/NO). Máximo 6 criterios concretos y medibles.\n"
            prompt += "  * La evidencia es la ficha de trabajo o producto resuelto individualmente.\n"
            prompt += "  * En el CIERRE incluye que el estudiante entrega su evidencia para verificarla con la lista de cotejo.\n"
        elif "Escala de valoración" in instrumento:
            prompt += "  * Genera criterios con puntaje (por ejemplo, del 1 al 4).\n"
            prompt += "  * La evidencia de aprendizaje debe poder puntuarse según esa escala.\n"
        elif "Ficha de observación" in instrumento:
            prompt += "  * Genera criterios orientados a la observación del desempeño.\n"
            prompt += "  * En el CIERRE menciona explícitamente que el docente circula y observa con la ficha de observación.\n"
    prompt += "\n"

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
        "8. El instrumento de evaluación detallado con criterios/ítems y niveles/escala (Si se sugirió uno, estructúralo según ese tipo).\n"
    )
    # También podemos sugerir al prompt de recursos que agregue el instrumento en "evaluacionFormativa" si es posible,
    # aunque la estructura actual pide preguntas/respuestas/criterios. Le daremos más contexto.
    prompt += "Nota: La evaluación formativa y el instrumento generado deben reflejar el instrumento de evaluación seleccionado si se indicó alguno.\n"
    return prompt
