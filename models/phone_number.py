import logging
import uuid

import requests
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def generate_uuid():
    """Generate a random UUID string for verify_token"""
    return str(uuid.uuid4())


class PhoneNumber(models.Model):
    """WhatsApp Business Phone Number"""
    API_TYPE_CHOICES = (
        ('official', _('Official WhatsApp Business API')),
        ('waha', _('WAHA API')),
    )

    display_name = models.CharField(_("Display Name"), max_length=100)
    phone_number = models.CharField(_("Phone Number"), max_length=20, unique=True)
    api_type = models.CharField(_("API Type"), max_length=10, choices=API_TYPE_CHOICES, default='official')

    # Official WhatsApp Business API fields
    phone_number_id = models.CharField(_("Phone Number ID"), max_length=100, blank=True, null=True)
    business_account_id = models.CharField(_("Business Account ID"), max_length=100, blank=True)
    access_token = models.CharField(_("Access Token"), max_length=255, blank=True,
                                    help_text=_("Token used for API authentication"))
    business_id = models.CharField(_("Facebook Business ID"), max_length=100, blank=True, null=True,
                                  help_text=_("Facebook Business ID for template management"))
    waba_id = models.CharField(_("WhatsApp Business Account ID"), max_length=100, blank=True, null=True,
                              help_text=_("WhatsApp Business Account ID for template management"))

    # WAHA API fields
    waha_endpoint = models.URLField(_("WAHA API Endpoint"), blank=True, null=True,
                                    help_text=_("Full URL to WAHA API (e.g., http://localhost:3000)"))
    waha_username = models.CharField(_("WAHA Username"), max_length=100, blank=True, null=True)
    waha_password = models.CharField(_("WAHA Password"), max_length=100, blank=True, null=True)
    waha_session = models.CharField(_("WAHA Session"), max_length=100, default="default")

    is_active = models.BooleanField(_("Is Active"), default=True)

    # Configuration status
    is_configured = models.BooleanField(_("Configuration Complete"), default=False,
                                        help_text=_("Check when you've completed all the configuration steps"))
    verify_token = models.CharField(_("Webhook Verify Token"), max_length=64, blank=True,
                                    help_text=_("Token used to verify webhook requests from WhatsApp"),
                                    default=generate_uuid)
    webhook_token = models.CharField(_("Webhook URL Token"), max_length=64, blank=True,
                                     help_text=_("Token used to secure the webhook URL"),
                                     default=generate_uuid)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("WhatsApp Phone Number")
        verbose_name_plural = _("WhatsApp Phone Numbers")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.display_name} ({self.phone_number})"

    def is_waha_api(self):
        """Check if this phone number uses WAHA API"""
        return self.api_type == 'waha'

    def is_official_api(self):
        """Check if this phone number uses official WhatsApp Business API"""
        return self.api_type == 'official'

    def send_message(self, to_number, message_text=None, template_name=None, template_params=None, media_url=None,
                     media_type=None, template=None):
        """
        Send a message using this phone number and create a message record
        
        Args:
            to_number: The recipient's phone number
            message_text: Text message content
            template_name: Name of the template to use
            template_params: Parameters for the template
            media_url: URL of media to send
            media_type: Type of media (image, audio, video, document)
            template: Template instance (optional)
        """
        if self.is_official_api() and not self.access_token:
            raise ValueError("Access token is required to send messages with official WhatsApp API")

        if self.is_waha_api() and not (self.waha_endpoint and self.waha_username and self.waha_password):
            raise ValueError("WAHA API endpoint, username and password are required")

        # Import Message locally to avoid circular imports
        from django.apps import apps
        Message = apps.get_model('whatsapp', 'Message')
        Contact = apps.get_model('whatsapp', 'Contact')

        # Get or create contact
        contact, created = Contact.objects.get_or_create(
            phone_number=to_number,
            defaults={'name': to_number}  # Use phone number as name initially
        )

        # Create a message record first
        message = Message.create_outgoing_message(
            phone_number=self,
            to_number=to_number,
            contact=contact,
            message_text=message_text,
            template_name=template_name,
            template_params=template_params,
            media_url=media_url,
            media_type=media_type,
            template=template
        )

        # The signal will handle sending the message
        return message

    def _send_message_without_record(self, to_number, message_text=None, template_name=None, template_params=None,
                                     media_url=None, media_type=None, instance=None):
        """
        Internal method to send a message without creating a new record
        Used by the signal handler to update an existing message
        """
        if self.is_official_api():
            return self._send_official_api_message(
                to_number, message_text, template_name, template_params,
                media_url, media_type, instance
            )
        elif self.is_waha_api():
            return self._send_waha_api_message(
                to_number, message_text, template_name, template_params,
                media_url, media_type, instance
            )
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def _send_official_api_message(self, to_number, message_text=None, template_name=None, template_params=None,
                                   media_url=None, media_type=None, instance=None):
        """Send message using official WhatsApp Business API"""
        if not self.access_token:
            raise ValueError("Access token is required to send messages")

        api_url = f"{settings.WHATSAPP_API_URL}/{self.phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        # Prepare message payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
        }

        # Handle different message types
        if message_text:
            payload["type"] = "text"
            payload["text"] = {"body": message_text}
        elif template_name:
            payload["type"] = "template"
            if not template_name:
                raise ValueError("Template name is required")

            template_data = {
                "name": template_name,
                **(template_params or {}),
            }

            payload["template"] = template_data
        elif media_url and media_type:
            payload["type"] = media_type
            media_payload = {
                "link": media_url
            }

            # Add caption for image, video, and document messages if provided
            if media_type in ["image", "video", "document"] and message_text:
                media_payload["caption"] = message_text

            # Add filename for document messages if available
            if media_type == "document" and media_url:
                # Extract filename from URL if not explicitly provided
                filename = media_url.split("/")[-1]
                media_payload["filename"] = filename

            payload[media_type] = media_payload
        else:
            raise ValueError("Either message_text, template_name, or media_url must be provided")

        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response_data = response.json()

            if response.status_code == 200:
                # Update the existing message record if provided
                if instance:
                    instance.message_id = response_data.get('messages', [{}])[0].get('id', '')
                    instance.status = 'sent'
                    instance.save(update_fields=['message_id', 'status'])
                return response_data
            else:
                logger.error(f"Failed to send WhatsApp message: {response_data}")
                if instance:
                    instance.status = 'failed'
                    instance.save(update_fields=['status'])
                raise Exception(
                    f"Failed to send WhatsApp message: {response_data.get('error', {}).get('message', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            if instance:
                instance.status = 'failed'
                instance.save(update_fields=['status'])
            raise

    def _send_waha_api_message(self, to_number, message_text=None, template_name=None, template_params=None,
                               media_url=None, media_type=None, instance=None):
        """Send message using WAHA API"""
        if not (self.waha_endpoint and self.waha_username and self.waha_password):
            raise ValueError("WAHA API endpoint, username and password are required")

        # Get contact to check for whatsapp_chat_id
        from django.apps import apps
        Contact = apps.get_model('whatsapp', 'Contact')

        try:
            contact = Contact.objects.get(phone_number=to_number)
            chat_id = contact.whatsapp_chat_id or to_number
        except Contact.DoesNotExist:
            chat_id = to_number

        # Import WAHA service
        from superapp.apps.whatsapp.services.waha import WAHAService

        waha_service = WAHAService(
            endpoint=self.waha_endpoint,
            username=self.waha_username,
            password=self.waha_password,
            session=self.waha_session
        )

        try:
            if message_text:
                response_data = waha_service.send_text(chat_id, message_text)
            elif media_url and media_type:
                if media_type == 'image':
                    response_data = waha_service.send_image(chat_id, media_url)
                elif media_type == 'document':
                    response_data = waha_service.send_document(chat_id, media_url)
                elif media_type == 'video':
                    response_data = waha_service.send_video(chat_id, media_url)
                elif media_type == 'audio':
                    response_data = waha_service.send_audio(chat_id, media_url)
                else:
                    raise ValueError(f"Unsupported media type for WAHA API: {media_type}")
            else:
                # WAHA doesn't support templates in the same way as official API
                raise ValueError("WAHA API only supports text and media messages")

            if response_data.get('success'):
                if instance:
                    instance.message_id = response_data.get('id', '')
                    instance.status = 'sent'
                    instance.save(update_fields=['message_id', 'status'])
                return response_data
            else:
                logger.error(f"Failed to send WAHA message: {response_data}")
                if instance:
                    instance.status = 'failed'
                    instance.save(update_fields=['status'])
                raise Exception(f"Failed to send WAHA message: {response_data.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error sending WAHA message: {str(e)}")
            if instance:
                instance.status = 'failed'
                instance.save(update_fields=['status'])
            raise

    def fetch_templates(self):
        """
        Fetch message templates from WhatsApp Business API
        
        Returns:
            list: List of templates fetched from the API
            or None if the API call fails
        """
        if not self.is_official_api():
            logger.warning(f"Cannot fetch templates: Phone number {self.id} is not using official WhatsApp API")
            return None

        if not self.access_token:
            logger.warning(f"Cannot fetch templates: Phone number {self.id} has no access token")
            return None

        if not self.business_account_id:
            logger.warning(f"Cannot fetch templates: Phone number {self.id} has no business account ID")
            return None

        api_url = f"{settings.WHATSAPP_API_URL}/{self.business_account_id}/message_templates"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(api_url, headers=headers)
            response_data = response.json()

            if response.status_code == 200:
                # Check if response_data is a dictionary and has 'data' key
                if isinstance(response_data, dict) and 'data' in response_data:
                    templates = response_data.get('data', [])
                elif isinstance(response_data, list):
                    # Some API versions might return a list directly
                    templates = response_data
                else:
                    logger.error(f"Unexpected response format: {response_data}")
                    return None

                # Import Template model locally to avoid circular imports
                from django.apps import apps
                Template = apps.get_model('whatsapp', 'Template')

                # Process each template
                imported_templates = []
                for template_data in templates:
                    if not isinstance(template_data, dict):
                        logger.error(f"Invalid template data format: {template_data}")
                        continue
                    template = Template.from_api_response(self, template_data)
                    imported_templates.append(template)

                return imported_templates
            else:
                logger.error(f"Failed to fetch WhatsApp templates: {response_data}")
                return None
        except Exception as e:
            logger.error(f"Error fetching WhatsApp templates: {str(e)}")
            return None

    def process_message_for_sending(self, message_instance):
        """
        Process a message instance for sending
        
        Args:
            message_instance: The Message instance to send
            
        Returns:
            bool: True if sending was successful, False otherwise
        """

        if not self.is_active:
            logger.warning(f"Cannot send message {message_instance.id}: Phone number {self.id} is not active")
            message_instance.status = 'failed'
            message_instance.save(update_fields=['status'])
            return False

        # Check API-specific requirements
        if self.is_official_api() and not self.access_token:
            logger.warning(f"Cannot send message {message_instance.id}: Phone number {self.id} has no access token")
            message_instance.status = 'failed'
            message_instance.save(update_fields=['status'])
            return False

        if self.is_waha_api() and not (self.waha_endpoint and self.waha_username and self.waha_password):
            logger.warning(
                f"Cannot send message {message_instance.id}: Phone number {self.id} missing WAHA API credentials")
            message_instance.status = 'failed'
            message_instance.save(update_fields=['status'])
            return False

        try:
            # Determine message type and send accordingly
            if message_instance.message_type == 'text':
                # Don't create a new message record since we're updating this one
                self._send_message_without_record(
                    to_number=message_instance.to_number,
                    message_text=message_instance.content,
                    instance=message_instance
                )
            elif message_instance.message_type == 'template':
                # Templates are only supported by official API
                if self.is_waha_api():
                    logger.warning(
                        f"Cannot send template message {message_instance.id}: WAHA API doesn't support templates")
                    message_instance.status = 'failed'
                    message_instance.save(update_fields=['status'])
                    return False

                # Get template name and parameters
                template_name = message_instance.template.name
                template_params = message_instance.template_variables

                if not template_name:
                    logger.warning(f"Cannot send template message {message_instance.id}: No template name provided")
                    message_instance.status = 'failed'
                    message_instance.save(update_fields=['status'])
                    return False

                self._send_message_without_record(
                    to_number=message_instance.to_number,
                    template_name=template_name,
                    template_params=template_params,
                    instance=message_instance
                )
            elif message_instance.message_type in ['image', 'audio', 'video', 'document']:
                self._send_message_without_record(
                    to_number=message_instance.to_number,
                    media_url=message_instance.media_file.url if message_instance.media_file else None,
                    media_type=message_instance.message_type,
                    instance=message_instance
                )
            else:
                logger.warning(f"Unsupported message type: {message_instance.message_type}")
                message_instance.status = 'failed'
                message_instance.save(update_fields=['status'])
                return False

            return True

        except Exception as e:
            logger.error(f"Error sending message {message_instance.id}: {str(e)}")
            message_instance.status = 'failed'
            message_instance.save(update_fields=['status'])
            return False
