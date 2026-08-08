import os
import time
import json
import logging
import httpx
from fastapi import APIRouter, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import Response, JSONResponse

from database import (save_session_input, save_generated_session, update_session_status,
                      get_whatsapp_state, save_whatsapp_state, clear_whatsapp_state)
from utils import normalize_session_input
from services import generate_lesson_result


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Metodo GET para verificacion del webhook de WhatsApp (Meta)."""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "eduai_verify_token")
    
    if hub_mode == "subscribe":
        if hub_verify_token == verify_token:
            logger.info("Webhook verificado exitosamente!")
            return Response(content=hub_challenge, media_type="text/plain")
        else:
            logger.warning("Fallo en verificacion de webhook: token no coincide.")
            raise HTTPException(status_code=403, detail="Verification token mismatch")
    
    logger.warning("Fallo en verificacion de webhook: modo invalido.")
    raise HTTPException(status_code=400, detail="Invalid hub.mode")


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Metodo POST para recibir los mensajes de WhatsApp."""
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error al decodificar JSON del webhook: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # Loguear evento recibido para propositos de depuracion
    logger.info(f"Webhook recibido: {json.dumps(payload)}")

    if payload.get("object") == "whatsapp_business_account":
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for message in value.get("messages", []):
                        if message.get("type") == "text":
                            from_phone = message.get("from")
                            message_body = message.get("text", {}).get("body")
                            phone_number_id = value.get("metadata", {}).get("phone_number_id")
                            
                            if from_phone and message_body:
                                logger.info(f"Mensaje de WhatsApp de {from_phone}: {message_body}")
                                # Agregar tarea en segundo plano para procesar la conversacion e interactuar
                                background_tasks.add_task(
                                    handle_whatsapp_flow_async,
                                    phone_number_id,
                                    from_phone,
                                    message_body
                                )
                                
        return JSONResponse(content={"status": "success"})
    
    return JSONResponse(content={"status": "ignored"})


async def handle_whatsapp_flow_async(phone_number_id: str, from_phone: str, message_body: str):
    """Maneja el flujo conversacional interactivo paso a paso."""
    body_clean = message_body.strip()
    body_lower = body_clean.lower()

    # Cancelar o reiniciar el flujo
    if body_lower in ["cancelar", "reiniciar", "salir", "/start"]:
        clear_whatsapp_state(from_phone)
        await send_whatsapp_message(phone_number_id, from_phone, "❌ Proceso cancelado. Escribe cualquier mensaje para iniciar una nueva sesión de aprendizaje.")
        return

    # Consultar estado actual
    state = get_whatsapp_state(from_phone)

    if not state:
        # Si el usuario escribe algo para empezar
        if body_lower in ["crear", "sesion", "hola", "bot", "ayuda", "empezar", "crear sesion"]:
            save_whatsapp_state(from_phone, step=1)
            welcome_text = (
                "🤖 *¡Hola! Bienvenido al asistente de EduAI.* 🤖\n\n"
                "Te guiaré paso a paso para estructurar tu sesión de aprendizaje.\n\n"
                "Para comenzar, escribe el **tema o título** de la sesión (ej: _Las plantas y sus partes_):"
            )
            await send_whatsapp_message(phone_number_id, from_phone, welcome_text)
        else:
            # Si escribe texto libre directo y no un comando de inicio, procesamos directamente con IA (flujo rápido)
            await process_whatsapp_message_async(phone_number_id, from_phone, message_body=message_body)
        return

    step = state["step"]

    if step == 1:
        # Guardar tema y preguntar por el grado
        save_whatsapp_state(from_phone, step=2, tema=body_clean)
        msg = (
            f"📝 *Tema registrado:* {body_clean}\n\n"
            "¿Para qué **grado o nivel** es la sesión? (ej: _1ro de Secundaria_, _5to de Primaria_):"
        )
        await send_whatsapp_message(phone_number_id, from_phone, msg)

    elif step == 2:
        # Guardar grado y preguntar por la duracion
        save_whatsapp_state(from_phone, step=3, grado=body_clean)
        msg = (
            f"🏫 *Grado registrado:* {body_clean}\n\n"
            "¿Cuál es la **duración** estimada de la clase? (ej: _2 horas_, _90 minutos_):"
        )
        await send_whatsapp_message(phone_number_id, from_phone, msg)

    elif step == 3:
        # Guardar duracion y preguntar por la competencia
        save_whatsapp_state(from_phone, step=4, duracion=body_clean)
        msg = (
            f"⏱️ *Duración registrada:* {body_clean}\n\n"
            "Selecciona la **competencia** matemática de la sesión escribiendo el número correspondiente (1-4):\n\n"
            "1️⃣ Resuelve problemas de cantidad\n"
            "2️⃣ Resuelve problemas de regularidad, equivalencia y cambio\n"
            "3️⃣ Resuelve problemas de forma, movimiento y localización\n"
            "4️⃣ Resuelve problemas de gestión de datos e incertidumbre"
        )
        await send_whatsapp_message(phone_number_id, from_phone, msg)

    elif step == 4:
        # Guardar competencia y preguntar por el contexto
        comp_map = {
            "1": "Resuelve problemas de cantidad",
            "2": "Resuelve problemas de regularidad, equivalencia y cambio",
            "3": "Resuelve problemas de forma, movimiento y localización",
            "4": "Resuelve problemas de gestión de datos e incertidumbre",
        }
        competencia = comp_map.get(body_clean) or body_clean
        save_whatsapp_state(from_phone, step=5, competencia=competencia)
        msg = (
            f"🎯 *Competencia registrada:* {competencia}\n\n"
            "Por último, escribe una descripción del **contexto sociocultural** o problemas de tu aula escolar (o escribe *no* para omitirlo):"
        )
        await send_whatsapp_message(phone_number_id, from_phone, msg)

    elif step == 5:
        # Guardar contexto, limpiar estado e iniciar generacion asincrona
        contexto = "" if body_lower == "no" else body_clean
        save_whatsapp_state(from_phone, step=6, contexto=contexto)
        
        # Recuperar estado completo
        full_state = get_whatsapp_state(from_phone)
        clear_whatsapp_state(from_phone)

        msg = "¡Excelente! He recopilado todos los datos. Iniciando la generación de tu sesión con IA... ⏳"
        await send_whatsapp_message(phone_number_id, from_phone, msg)

        # Lanzar proceso de IA en segundo plano
        await process_whatsapp_message_async(
            phone_number_id,
            from_phone,
            state_data=full_state
        )


async def process_whatsapp_message_async(
    phone_number_id: str,
    from_phone: str,
    message_body: str = None,
    state_data: dict = None
):
    """Procesa el mensaje o el estado recopilado en segundo plano, genera la sesion y responde."""
    session_id = f"wa_{from_phone}_{int(time.time())}"

    if state_data:
        # Si viene del flujo paso a paso
        normalized_data = {
            "tema": state_data.get("tema", ""),
            "titulo": state_data.get("tema", ""),
            "docente": "Bot de WhatsApp",
            "fecha": "",
            "grado": state_data.get("grado", ""),
            "seccion": "",
            "competenciasSeleccionadas": [state_data.get("competencia")] if state_data.get("competencia") else [],
            "capacidades": [],
            "ciclo": "",
            "contexto": state_data.get("contexto", ""),
            "duracion": state_data.get("duracion", "2 horas"),
            "horasClase": 2,
            "enfoqueTransversal": "",
            "competenciaTransversal": "",
            "materialesDisponibles": "",
            "idioma": "español"
        }
    else:
        # Si es un flujo directo de texto libre
        initial_text = "¡Hola! Estoy generando tu sesión de aprendizaje con IA. Esto tomará unos segundos... ⏳"
        await send_whatsapp_message(phone_number_id, from_phone, initial_text)
        normalized_data = normalize_session_input(message_body)
    
    try:
        # Registrar entrada en la base de datos local
        save_session_input(session_id, normalized_data, source="whatsapp", status="generating")
        
        # 3. Llamar al servicio de generacion de lecciones (Gemini)
        result = await generate_lesson_result(session_id, normalized_data)
        
        if "error" in result:
            error_msg = f"Lo siento, ocurrió un error al generar la sesión: {result['error']}"
            await send_whatsapp_message(phone_number_id, from_phone, error_msg)
            return

        # 4. Sincronizar sesion con el microservicio de autenticacion global (PostgreSQL)
        await sync_session_to_auth(session_id, normalized_data, result)
        
        # 5. Generar y enviar el documento PDF al usuario
        pdf_url = os.getenv("PDF_RENDER_API_URL", "https://api.sesionmas.online/api/pdf")


        try:
            # Consolidar datos de la sesion para la API de renderizado PDF
            session_data = {
                **normalized_data,
                **result,
                "session_id": session_id,
                "id": session_id,
                "is_public": True,
                "author_name": "Bot de WhatsApp",
                "likes": 0,
            }
            # Formatear nombre de archivo seguro
            safe_theme = "".join(c if c.isalnum() else "_" for c in normalized_data.get("tema", "aprendizaje"))
            safe_filename = f"Sesion_{safe_theme}.pdf"
            
            logger.info(f"Llamando a pdf-render en: {pdf_url}/generate-pdf para la sesion {session_id}")
            async with httpx.AsyncClient() as client:
                pdf_resp = await client.post(f"{pdf_url}/generate-pdf", json={"data": session_data}, timeout=45.0)
                if pdf_resp.status_code == 200:
                    logger.info(f"PDF generado exitosamente ({len(pdf_resp.content)} bytes). Cargando a Meta...")
                    media_id = await upload_whatsapp_media(phone_number_id, pdf_resp.content, safe_filename)
                    if media_id:
                        caption = f"✨ *¡Sesión de Aprendizaje Lista!* ✨\n\nAquí tienes tu planificación completa para *{normalized_data.get('tema')}* ({normalized_data.get('grado')}) generada por *EduAI*. 🚀\n\n¡Espero que te sea de gran utilidad en el aula!"
                        await send_whatsapp_document(phone_number_id, from_phone, media_id, safe_filename, caption)
                    else:
                        logger.error("No se pudo obtener el media_id de Meta.")
                else:
                    logger.error(f"Fallo en pdf-render ({pdf_resp.status_code}): {pdf_resp.text}")
        except Exception as pdf_err:
            logger.exception(f"Error critico en la generacion/envio del archivo PDF: {pdf_err}")

        # 6. Dar formato al resumen y enviar mensaje de respuesta final al usuario (con link de la web)
        summary = format_lesson_summary(result, session_id)
        await send_whatsapp_message(phone_number_id, from_phone, summary)
        
    except Exception as e:
        logger.exception("Error en la tarea en segundo plano para procesar mensaje de WhatsApp")
        error_msg = "Lo siento, ocurrió un error inesperado al procesar tu solicitud. Por favor intenta de nuevo más tarde."
        await send_whatsapp_message(phone_number_id, from_phone, error_msg)




async def send_whatsapp_message(phone_number_id: str, to_phone: str, text_message: str):
    """Cliente HTTP para enviar mensajes de texto usando la API de WhatsApp Cloud (Meta)."""
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    if not whatsapp_token:
        logger.error("La variable WHATSAPP_TOKEN no esta configurada en el entorno.")
        return
        
    p_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not p_id:
        logger.error("No se dispone del ID del numero de telefono de WhatsApp.")
        return

    url = f"https://graph.facebook.com/v20.0/{p_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": text_message},
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(f"Fallo al enviar mensaje a WhatsApp. Estatus: {response.status_code}, Cuerpo: {response.text}")
            else:
                logger.info(f"Mensaje de WhatsApp enviado exitosamente a {to_phone}")
        except Exception as e:
            logger.error(f"Excepcion capturada al enviar mensaje a WhatsApp: {e}")


async def upload_whatsapp_media(phone_number_id: str, media_bytes: bytes, filename: str) -> str:
    """Sube un archivo binario a Meta y devuelve su media_id."""
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    if not whatsapp_token:
        logger.error("La variable WHATSAPP_TOKEN no está configurada en el entorno.")
        return None

    p_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not p_id:
        logger.error("No se dispone del ID del número de teléfono de WhatsApp.")
        return None

    url = f"https://graph.facebook.com/v20.0/{p_id}/media"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}"
    }
    
    files = {
        "file": (filename, media_bytes, "application/pdf")
    }
    data = {
        "messaging_product": "whatsapp",
        "type": "application/pdf"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, data=data, files=files)
            if response.status_code == 200:
                resp_json = response.json()
                media_id = resp_json.get("id")
                logger.info(f"Archivo PDF subido exitosamente a Meta. Media ID: {media_id}")
                return media_id
            else:
                logger.error(f"Error al subir media a Meta. Estatus: {response.status_code}, Cuerpo: {response.text}")
        except Exception as e:
            logger.exception(f"Excepción al subir media a Meta: {e}")
    return None


async def send_whatsapp_document(phone_number_id: str, to_phone: str, media_id: str, filename: str, caption: str):
    """Envia un documento cargado en Meta usando su media_id."""
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    if not whatsapp_token:
        return
        
    p_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not p_id:
        return

    url = f"https://graph.facebook.com/v20.0/{p_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename,
            "caption": caption
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(f"Fallo al enviar PDF a WhatsApp. Estatus: {response.status_code}, Cuerpo: {response.text}")
            else:
                logger.info(f"PDF enviado exitosamente a {to_phone}")
        except Exception as e:
            logger.error(f"Excepcion al enviar PDF: {e}")


async def sync_session_to_auth(session_id: str, normalized_data: dict, final_lesson: dict):

    """Sincroniza la sesion de aprendizaje generada con el backend de autenticacion global."""
    auth_url = os.getenv("AUTH_URL", "https://eduai-auth-1.onrender.com")
    email = "whatsapp@eduai.com"
    password = "whatsapp_default_secure_password_123!"
    full_name = "Bot de WhatsApp"

    async with httpx.AsyncClient() as client:
        # Intentar asegurar que el usuario de WhatsApp exista en el sistema global
        try:
            reg_payload = {
                "email": email,
                "password": password,
                "full_name": full_name,
            }
            reg_response = await client.post(f"{auth_url}/register", json=reg_payload)
            if reg_response.status_code == 200:
                logger.info("Usuario whatsapp@eduai.com registrado exitosamente en el backend global.")
            elif reg_response.status_code == 400:
                logger.info("El usuario whatsapp@eduai.com ya se encuentra registrado.")
            else:
                logger.warning(f"La peticion de registro devolvio estatus {reg_response.status_code}: {reg_response.text}")
        except Exception as e:
            logger.error(f"Error al asegurar el registro del usuario de WhatsApp: {e}")

        # Preparar datos unificados de la sesion
        session_data = {
            **normalized_data,
            **final_lesson,
            "session_id": session_id,
            "id": session_id,
            "is_public": True,
            "author_name": full_name,
            "likes": 0,
        }
        
        save_payload = {
            "user_id": email,
            "session_data": session_data,
        }
        
        try:
            save_response = await client.post(f"{auth_url}/save-session", json=save_payload)
            if save_response.status_code == 200:
                logger.info(f"Sesion {session_id} sincronizada con exito en el backend global.")
            else:
                logger.error(f"Error al sincronizar sesion {session_id}. Estatus: {save_response.status_code}, Cuerpo: {save_response.text}")
        except Exception as e:
            logger.error(f"Excepcion capturada al sincronizar sesion: {e}")


def format_lesson_summary(lesson_data: dict, session_id: str) -> str:
    """Da formato a la respuesta en texto legible para WhatsApp con un vinculo a la aplicacion web."""
    datos = lesson_data.get("datosGenerales") or {}
    title = datos.get("titulo") or lesson_data.get("titulo") or lesson_data.get("tema") or "Sesión de Aprendizaje"
    grado = datos.get("grado") or "Secundaria"
    duracion = datos.get("duracion") or "2 horas"
    proposito = lesson_data.get("propositoSesion") or "No especificado"
    
    comp_list = lesson_data.get("competenciasSeleccionadas") or []
    competencies = ", ".join(comp_list) if comp_list else "No especificadas"

    frontend_url = os.getenv("FRONTEND_URL", "https://sesionmas.online")

    link = f"{frontend_url}/repositorio/{session_id}"

    summary = (
        f"✨ *Sesión de Aprendizaje Generada* ✨\n\n"
        f"📝 *Título:* {title}\n"
        f"🏫 *Grado:* {grado}\n"
        f"⏱️ *Duración:* {duracion}\n"
        f"🎯 *Propósito:* {proposito}\n"
        f"📚 *Competencias:* {competencies}\n\n"
        f"🔗 Puedes ver y descargar tu sesión completa aquí:\n{link}\n\n"
        f"¡Gracias por usar EduAI! 🚀"
    )
    return summary
