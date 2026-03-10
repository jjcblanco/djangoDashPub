import requests
import logging
from ..models import GlobalSettings

logger = logging.getLogger(__name__)

def send_telegram_message(message):
    """
    Envía un mensaje a Telegram utilizando las credenciales de GlobalSettings.
    """
    try:
        settings, _ = GlobalSettings.objects.get_or_create(id=1)
        
        if not settings.notifications_enabled:
            return False
            
        token = settings.telegram_token
        chat_id = settings.telegram_chat_id
        
        if not token or not chat_id:
            logger.warning("Telegram notificado pero falto Token o Chat ID.")
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
