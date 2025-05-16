# Import all signals to ensure they're connected
from superapp.apps.whatsapp.signals.fetch_templates_on_phone_number_save import *
from superapp.apps.whatsapp.signals.send_outgoing_message import *

__all__ = []
