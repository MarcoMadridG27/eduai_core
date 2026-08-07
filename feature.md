Actúa como un arquitecto senior especializado en Retrieval-Augmented Generation (RAG), FastAPI, Google Gemini, Qdrant y sistemas de IA para educación.

Debes diseñar una arquitectura profesional para un sistema RAG que genere sesiones de aprendizaje alineadas al Currículo Nacional del Perú (MINEDU).

El objetivo es que el sistema pueda procesar documentos oficiales del MINEDU y posteriormente responder consultas de docentes utilizando Retrieval-Augmented Generation.

La solución debe ser modular, escalable y preparada para producción.

=========================
OBJETIVO GENERAL
=========================

Construir un pipeline completo desde la carga de documentos PDF hasta la generación de respuestas usando Gemini y Qdrant.

La arquitectura deberá ejecutarse sobre una instancia EC2 utilizando Docker.

=========================
FLUJO COMPLETO
=========================

El flujo debe contemplar las siguientes etapas.

───────────────────────────────
FASE 1
INGESTA DE DOCUMENTOS
───────────────────────────────

Los documentos oficiales serán almacenados en carpetas organizadas.(NO ES INDISPENSABLE YA QUE NO SE VAN A COMMITEAR), los pdfs estan en la carpeta pdfs.

Ejemplo:

knowledge/

    curriculum/

        curriculum_nacional.pdf

    inicial/

        programa_curricular.pdf

    primaria/

        programa_curricular.pdf

    secundaria/

        programa_curricular.pdf

        matematica/

        comunicacion/

        ciencia/

    evaluacion/

    fasciculos/

    guias/

Cada documento tendrá información sobre:

- nivel
- área
- año
- versión
- tipo de documento

───────────────────────────────
FASE 2
EXTRACCIÓN DEL PDF
───────────────────────────────

Utilizar Docling.

El sistema debe:

- abrir PDF
- detectar estructura
- extraer texto
- conservar títulos
- conservar tablas
- conservar listas
- conservar encabezados
- exportar a Markdown o estructura equivalente

No usar OCR salvo que el documento sea escaneado.

Si el PDF ya contiene texto, evitar OCR.

───────────────────────────────
FASE 3
LIMPIEZA
───────────────────────────────

Eliminar:

- encabezados repetidos
- pies de página
- números de página
- espacios innecesarios
- caracteres extraños

Mantener únicamente contenido pedagógico.

───────────────────────────────
FASE 4
CHUNKING
───────────────────────────────

No dividir únicamente por cantidad de caracteres.

Realizar chunking semántico.

Respetar:

Capítulos

Secciones

Competencias

Capacidades

Estándares

Desempeños

Orientaciones

Cada chunk debe tener aproximadamente entre 500 y 800 tokens.

Cada chunk debe conservar contexto suficiente para responder preguntas sin depender del chunk anterior.

───────────────────────────────
FASE 5
METADATA
───────────────────────────────

Cada chunk debe almacenar metadata.

Ejemplo

{
    id

    documento

    nivel

    ciclo

    grado

    area

    competencia

    capacidad

    tipo

    pagina_inicio

    pagina_fin

    año

    version

}

Esta metadata posteriormente será utilizada para realizar filtros en Qdrant.

───────────────────────────────
FASE 6
EMBEDDINGS
───────────────────────────────

Utilizar Voyage AI Embeddings.

La API Key de Voyage AI ya se encuentra configurada dentro del proyecto en:

eduai-core/.env

El sistema debe leer automáticamente la variable de entorno correspondiente y nunca almacenar la API Key en el código fuente.

Los embeddings deben generarse utilizando el modelo recomendado por Voyage AI para Retrieval-Augmented Generation (RAG).

Cada chunk debe convertirse en un embedding únicamente durante el proceso de indexación.

Nunca recalcular embeddings durante las consultas.

Por cada chunk se debe almacenar en Qdrant:

- embedding
- texto original
- metadata

El sistema debe estar diseñado de forma que, si en el futuro se desea cambiar el proveedor de embeddings (OpenAI, Gemini, Nomic, BAAI, etc.), únicamente sea necesario modificar una clase o servicio encargado de la generación de embeddings, sin afectar el resto del pipeline.

───────────────────────────────
FASE 7
chroma
───────────────────────────────

Desplegar Qdrant mediante Docker en una instancia EC2.

Persistir los datos mediante volumen.

Crear una colección llamada

curriculum_documents

Configurar:

HNSW

Cosine Similarity

Payload Index

Permitir filtros por metadata.

Ejemplos

nivel

grado

area

competencia

tipo

documento

───────────────────────────────
FASE 8
CONSULTA
───────────────────────────────

Cuando un usuario solicite una sesión:

Ejemplo

"Genera una sesión para Matemática de cuarto de primaria sobre fracciones."

El sistema debe:

1 generar embedding de la consulta

2 aplicar filtros

nivel = primaria

grado = cuarto

area = matemática

3 consultar Qdrant

4 recuperar Top K chunks

5 ordenar resultados

6 eliminar duplicados

───────────────────────────────
FASE 9
PROMPT BUILDER
───────────────────────────────

Construir automáticamente el prompt para Gemini.

Debe incluir:

Rol del sistema.

Consulta del usuario.

Contexto recuperado.

Instrucciones.

Formato esperado.

Indicar explícitamente que la respuesta debe basarse únicamente en el contexto recuperado.

───────────────────────────────
FASE 10
GENERACIÓN
───────────────────────────────

Enviar el prompt a Gemini 2.5.

Generar:

Sesión de aprendizaje.

Competencias.

Capacidades.

Desempeños.

Criterios de evaluación.

Evidencias.

Instrumentos.

Actividades.

Recursos.

Materiales.

───────────────────────────────
FASE 11
OBSERVABILIDAD
───────────────────────────────

Integrar Langfuse.

Registrar:

prompt

respuesta

latencia

tokens

modelo

coste

chunks recuperados

score de similitud

=========================
REQUISITOS
=========================

Utilizar:

Python

FastAPI

Docling

Google Gemini

Qdrant

Docker

AWS EC2

Langfuse

No utilizar LangChain.

No utilizar LlamaIndex.

Implementar el pipeline directamente en Python para mantener el control total de cada etapa.

=========================
RESULTADO ESPERADO
=========================

Explicar detalladamente la arquitectura.

Mostrar el flujo completo.

Proponer la estructura de carpetas.

Explicar cómo organizar los módulos.

Mostrar el pipeline de indexación.

Mostrar el pipeline de consulta.

Explicar cómo diseñar los metadatos.

Explicar cómo optimizar el chunking.

Explicar cómo actualizar documentos sin volver a indexar todo.

Explicar cómo versionar documentos oficiales del MINEDU.

Explicar cómo desplegar Qdrant en Docker sobre EC2.

Explicar cómo conectar FastAPI con Qdrant y Gemini.

Explicar buenas prácticas para un sistema RAG en producción.