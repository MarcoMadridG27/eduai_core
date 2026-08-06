import os
import time
import json
import logging
import httpx
from fastapi import APIRouter, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import Response, JSONResponse

from database import save_session_input, save_generated_session, update_session_status
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
                                # Agregar tarea en segundo plano para procesar la generacion de la sesion
                                background_tasks.add_task(
                                    process_whatsapp_message_async,
                                    phone_number_id,
                                    from_phone,
                                    message_body
                                )
                                
        return JSONResponse(content={"status": "success"})
    
    return JSONResponse(content={"status": "ignored"})


async def process_whatsapp_message_async(phone_number_id: str, from_phone: str, message_body: str):
    """Procesa el mensaje recibido en segundo plano, genera la sesion y responde."""
    # 1. Enviar mensaje inicial al usuario indicando el inicio del proceso
    initial_text = "¡Hola! Estoy generando tu sesión de aprendizaje con IA. Esto tomará unos segundos... ⏳"
    await send_whatsapp_message(phone_number_id, from_phone, initial_text)

    # 2. Inicializar sesion en base de datos local SQLite
    session_id = f"wa_{from_phone}_{int(time.time())}"
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
        
        # 5. Dar formato al resumen y enviar mensaje de respuesta final al usuario
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

    frontend_url = os.getenv("FRONTEND_URL", "https://eduai-app.vercel.app")
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
