import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class WhatsAppAPIService:
    """
    Service for interacting with the WhatsApp Business API
    """
    
    @staticmethod
    def get_media_url(media_id, phone_number_id):
        """
        Get the URL for a media file using its ID
        """
        api_url = f"{settings.WHATSAPP_API_URL}/{media_id}"
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_API_TOKEN}'
        }
        
        try:
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                media_data = response.json()
                return media_data.get('url')
            else:
                logger.error(f"Failed to get media URL: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting media URL: {str(e)}")
            return None
    
    @staticmethod
    def download_media(media_url):
        """
        Download media from the given URL
        """
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_API_TOKEN}'
        }
        
        try:
            response = requests.get(media_url, headers=headers)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download media: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error downloading media: {str(e)}")
            return None
    
    @staticmethod
    def mark_message_as_read(message_id, phone_number_id):
        """
        Mark a message as read
        """
        api_url = f"{settings.WHATSAPP_API_URL}/{phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Failed to mark message as read: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error marking message as read: {str(e)}")
            return False
