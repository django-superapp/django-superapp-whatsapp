import base64
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class WAHAService:
    """
    Service for interacting with the WAHA API (WhatsApp HTTP API)
    """
    
    def __init__(self, endpoint, username, password, session="default"):
        """
        Initialize the WAHA service
        
        Args:
            endpoint: Full URL to WAHA API (e.g., http://localhost:3000)
            username: WAHA API username
            password: WAHA API password
            session: WAHA session name (default: "default")
        """
        self.endpoint = endpoint.rstrip('/')
        self.username = username
        self.password = password
        self.session = session
        
    def _get_auth_header(self):
        """Get the Basic Auth header for WAHA API"""
        auth_string = f"{self.username}:{self.password}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded_auth}"
        
    def _make_request(self, endpoint, method="GET", data=None):
        """Make a request to the WAHA API"""
        url = f"{self.endpoint}/api/{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self._get_auth_header()
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            if response.status_code in (200, 201):
                return response.json()
            else:
                logger.error(f"WAHA API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            logger.error(f"Error making WAHA API request: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def send_text(self, chat_id, text, link_preview=True):
        """
        Send a text message
        
        Args:
            chat_id: WhatsApp chat ID or phone number
            text: Message text
            link_preview: Whether to show link previews
            
        Returns:
            API response
        """
        # Ensure chat_id is properly formatted (should end with @c.us for individual chats)
        if chat_id and '@' not in chat_id:
            # Format as individual chat ID if not already formatted
            chat_id = f"{chat_id.replace('+', '').replace(' ', '')}@c.us"
            
        data = {
            "chatId": chat_id,
            "text": text,
            "linkPreview": link_preview,
            "session": self.session
        }
        return self._make_request("sendText", method="POST", data=data)
    
    def send_image(self, chat_id, image_url, caption=None):
        """Send an image message"""
        # Ensure chat_id is properly formatted
        if chat_id and '@' not in chat_id:
            chat_id = f"{chat_id.replace('+', '').replace(' ', '')}@c.us"
            
        data = {
            "chatId": chat_id,
            "image": image_url,
            "caption": caption or "",
            "session": self.session
        }
        return self._make_request("sendImage", method="POST", data=data)
    
    def send_document(self, chat_id, document_url, filename=None):
        """Send a document message"""
        # Ensure chat_id is properly formatted
        if chat_id and '@' not in chat_id:
            chat_id = f"{chat_id.replace('+', '').replace(' ', '')}@c.us"
            
        data = {
            "chatId": chat_id,
            "document": document_url,
            "filename": filename or "document",
            "session": self.session
        }
        return self._make_request("sendDocument", method="POST", data=data)
    
    def send_video(self, chat_id, video_url, caption=None):
        """Send a video message"""
        # Ensure chat_id is properly formatted
        if chat_id and '@' not in chat_id:
            chat_id = f"{chat_id.replace('+', '').replace(' ', '')}@c.us"
            
        data = {
            "chatId": chat_id,
            "video": video_url,
            "caption": caption or "",
            "session": self.session
        }
        return self._make_request("sendVideo", method="POST", data=data)
    
    def send_audio(self, chat_id, audio_url):
        """Send an audio message"""
        # Ensure chat_id is properly formatted
        if chat_id and '@' not in chat_id:
            chat_id = f"{chat_id.replace('+', '').replace(' ', '')}@c.us"
            
        data = {
            "chatId": chat_id,
            "audio": audio_url,
            "session": self.session
        }
        return self._make_request("sendAudio", method="POST", data=data)
    
    def get_chats(self):
        """Get all chats"""
        return self._make_request(f"getChats?session={self.session}", method="GET")
    
    def get_contacts(self):
        """Get all contacts"""
        return self._make_request(f"getContacts?session={self.session}", method="GET")
    
    def get_profile_picture(self, chat_id):
        """Get profile picture for a contact"""
        data = {
            "chatId": chat_id,
            "session": self.session
        }
        return self._make_request("getProfilePicture", method="POST", data=data)
        
    def get_session_status(self):
        """Get the status of the current session"""
        return self._make_request(f"sessions/{self.session}/status", method="GET")
    
    def start_session(self):
        """Start a new session or reconnect an existing one"""
        return self._make_request(f"sessions/{self.session}/start", method="POST")
    
    def stop_session(self):
        """Stop the current session"""
        return self._make_request(f"sessions/{self.session}/stop", method="POST")
    
    def configure_webhooks(self, webhook_url, events=None):
        """
        Configure webhooks for the WAHA API
        
        Args:
            webhook_url: URL to receive webhook events
            events: List of events to subscribe to (default: ["message"])
            
        Returns:
            API response
        """
        if events is None:
            events = ["message"]
        
        # Use the sessions API to update the session configuration with webhooks
        data = {
            "config": {
                "webhooks": [
                    {
                        "url": webhook_url,
                        "events": events
                    }
                ]
            }
        }
        
        return self._make_request(f"sessions/{self.session}", method="PUT", data=data)
