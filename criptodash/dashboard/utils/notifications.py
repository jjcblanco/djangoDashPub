import requests
import logging
from ..models import GlobalSettings

logger = logging.getLogger(__name__)

def send_telegram_message(message, token_override=None, chat_id_override=None, force=False):
    """
    Envía un mensaje a Telegram. 
    Permite overrides para pruebas antes de guardar en GlobalSettings.
    """
    try:
        settings, _ = GlobalSettings.objects.get_or_create(id=1)
        
        # Determinar credenciales (override vs DB)
        token = token_override if token_override else settings.telegram_token
        chat_id = chat_id_override if chat_id_override else settings.telegram_chat_id
        enabled = settings.notifications_enabled if not force else True
        
        print(f"DEBUG TELEGRAM: Intentando enviar. Enabled={enabled}, Force={force}")
        
        if not enabled:
            print("DEBUG TELEGRAM: Envío cancelado por estar deshabilitado globalmente.")
            return False
            
        if not token or not chat_id:
            print(f"DEBUG TELEGRAM: Faltan credenciales. Token={'SÍ' if token else 'NO'}, ChatID={'SÍ' if chat_id else 'NO'}")
            logger.warning("Telegram notificado pero falta Token o Chat ID.")
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        print(f"DEBUG TELEGRAM: URL: https://api.telegram.org/bot[REDACTED]/sendMessage")
        print(f"DEBUG TELEGRAM: Payload: {payload}")
        
        response = requests.post(url, data=payload, timeout=10)
        
        print(f"DEBUG TELEGRAM: Status Code: {response.status_code}")
        print(f"DEBUG TELEGRAM: Response Body: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Error enviando Telegram: {response.text}")
            return False
            
        return True
    except Exception as e:
        import traceback
        print(f"DEBUG TELEGRAM: EXCEPCIÓN: {str(e)}")
        print(traceback.format_exc())
        logger.error(f"Excepción al enviar Telegram: {e}")
        return False
