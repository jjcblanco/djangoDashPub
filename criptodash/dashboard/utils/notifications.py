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
        
        if not enabled:
            return False
            
        if not token or not chat_id:
            logger.warning("Telegram notificado pero falta Token o Chat ID.")
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Error enviando Telegram: {response.text}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Excepción al enviar Telegram: {e}")
        return False
