import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Message(models.Model):
    """
    Model to store WhatsApp messages (both incoming and outgoing)
    """
    DIRECTION_CHOICES = (
        ('incoming', _('Incoming')),
        ('outgoing', _('Outgoing')),
    )

    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('received', _('Received')),
        ('sent', _('Sent')),
        ('delivered', _('Delivered')),
        ('read', _('Read')),
        ('failed', _('Failed')),
    )

    MESSAGE_TYPE_CHOICES = (
        ('text', _('Text')),
        ('image', _('Image')),
        ('audio', _('Audio')),
        ('video', _('Video')),
        ('document', _('Document')),
        ('location', _('Location')),
        ('template', _('Template')),
        ('button', _('Button')),
        ('interactive', _('Interactive')),
    )

    # Use string reference to avoid circular import
    phone_number = models.ForeignKey('whatsapp.PhoneNumber', on_delete=models.CASCADE, related_name='messages')
    contact = models.ForeignKey('whatsapp.Contact', on_delete=models.SET_NULL, related_name='messages', null=True, blank=True)
    template = models.ForeignKey('whatsapp.Template', on_delete=models.SET_NULL, related_name='messages', null=True, blank=True)
    template_variables = models.JSONField(
        _("template variables"),
        default=dict,
        blank=True,
        null=True,
        help_text=_("Variables used in the template, including body parameters and button parameters"),
    )

    message_id = models.CharField(_("message ID"), max_length=255, unique=True, default=uuid.uuid4)
    conversation_id = models.CharField(_("conversation ID"), max_length=255, blank=True, null=True)
    from_number = models.CharField(_("from number"), max_length=50)
    to_number = models.CharField(_("to number"), max_length=50)
    direction = models.CharField(_("direction"), max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(_("message type"), max_length=20, choices=MESSAGE_TYPE_CHOICES)
    content = models.TextField(_("content"), blank=True, null=True)
    media_file = models.FileField(_("Media file"), upload_to='whatsapp_media/', blank=True, null=True)
    media_id = models.CharField(_("media ID"), max_length=255, blank=True, null=True)
    media_type = models.CharField(_("media type"), max_length=20, choices=MESSAGE_TYPE_CHOICES, blank=True, null=True)
    media_mime_type = models.CharField(_("media mime type"), max_length=50, blank=True, null=True)
    content_type = models.CharField(_("content type"), max_length=20, choices=MESSAGE_TYPE_CHOICES, blank=True, null=True)
    metadata = models.JSONField(_("metadata"), blank=True, null=True)
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True, null=True, blank=True)
    status = models.CharField(_("status"), max_length=10, choices=STATUS_CHOICES, default="received")
    raw_message = models.JSONField(_("raw message"), blank=True, null=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)
    error_code = models.CharField(_("error code"), max_length=50, blank=True, null=True)
    error_message = models.TextField(_("error message"), blank=True, null=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.direction.capitalize()} message {self.message_id}"
        
    @classmethod
    def create_outgoing_message(cls, phone_number, to_number, contact=None, message_text=None, template_name=None, 
                               template_params=None, media_file=None, media_type=None, template=None):
        """
        Create an outgoing message that will be automatically sent via signals
        
        Args:
            phone_number: The PhoneNumber instance to use for sending
            to_number: The recipient's phone number
            contact: The Contact instance (optional)
            message_text: Text message content
            template_name: Name of the template to use
            template_params: Parameters for the template
            media_file: File to be sent (optional)
            media_type: Type of media (image, audio, video, document)
            template: Template instance (optional)
            
        Returns:
            The created Message instance
        """
        import json
        
        if message_text:
            message_type = 'text'
            content = message_text
        elif template_name or template:
            message_type = 'template'
            
            # If template instance is provided, use it
            if template:
                template_name = template.name
                
            if template_params:
                content = json.dumps({"name": template_name, "params": template_params})
            else:
                content = template_name
        elif media_file and media_type:
            message_type = media_type
            content = ''
        else:
            raise ValueError("Either message_text, template_name, template, or media_url must be provided")
            
        return cls.objects.create(
            phone_number=phone_number,
            contact=contact,
            template=template,
            template_variables=template_params or {},
            from_number=phone_number.phone_number,
            to_number=to_number,
            direction='outgoing',
            message_type=message_type,
            content=content,
            media_file=media_file,
            status='pending'  # Set as pending so the signal will send it
        )
        
    @classmethod
    def create_outgoing_template_message(cls, phone_number, to_number, contact=None, template_name=None, 
                                        template_variables=None, template=None):
        """
        Create an outgoing template message with structured variables that will be automatically sent via signals
        
        Args:
            phone_number: The PhoneNumber instance to use for sending
            to_number: The recipient's phone number
            contact: The Contact instance (optional)
            template_name: Name of the template to use
            template_variables: Structured variables for the template following WhatsApp API format
                Example format:
                {
                  "language": {
                    "code": "ro"
                  },
                  "components": [
                    {
                      "type": "body",
                      "parameters": [
                        {
                          "type": "text",
                          "parameter_name": "client_name",
                          "text": "Client Name"
                        },
                        ...
                      ]
                    },
                    {
                      "type": "button",
                      "sub_type": "url",
                      "index": "0",
                      "parameters": [
                        {
                          "type": "text",
                          "text": "https://example.com"
                        }
                      ]
                    }
                  ]
                }
            template: Template instance (optional)
            
        Returns:
            The created Message instance
        """
        import json
        
        message_type = 'template'
        
        # If template instance is provided, use it
        if template:
            template_name = template.name
            
        if not template_name:
            raise ValueError("template_name must be provided")
            
        # Create content with template name and structured variables
        content = json.dumps({
            "name": template_name,
            "language": template_variables.get("language", {"code": settings.DEFAULT_LANGUAGE_CODE}),
            "components": template_variables.get("components", [])
        })
            
        return cls.objects.create(
            phone_number=phone_number,
            contact=contact,
            template=template,
            template_variables=template_variables,
            from_number=phone_number.phone_number,
            to_number=to_number,
            direction='outgoing',
            message_type=message_type,
            content=content,
            status='pending'  # Set as pending so the signal will send it
        )

    def retry_send(self):
        """
        Retry sending a failed or pending message.
        
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if self.direction != 'outgoing':
            logger.warning(f"Cannot retry message {self.id}: Not an outgoing message")
            return False
            
        if not self.phone_number:
            logger.warning(f"Cannot retry message {self.id}: No phone number associated")
            return False
        
        try:
            # Update status to pending
            self.status = 'pending'
            self.save(update_fields=['status'])
            
            # Use the phone number's process_message_for_sending method
            return self.phone_number.process_message_for_sending(self)
                
        except Exception as e:
            logger.exception(f"Error retrying message {self.id}: {str(e)}")
            self.status = 'failed'
            self.save(update_fields=['status'])
            return False

