# Import models in the correct order to avoid circular imports
from .phone_number import PhoneNumber
from .contact import Contact
from .message import Message
from .template import Template

# Import signals to ensure they're connected
from superapp.apps.whatsapp.signals import *

__all__ = ['PhoneNumber', 'Contact', 'Message', 'Template']
