import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from superapp.apps.whatsapp.models.message import Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def send_outgoing_message(sender, instance, created, **kwargs):
    """
    Signal handler to automatically send outgoing messages when they are created
    """
    if created and instance.direction == 'outgoing' and instance.status == 'pending':
        # Get the phone number associated with this message
        phone_number = instance.phone_number

        # Use the phone number's process_message_for_sending method
        phone_number.process_message_for_sending(instance)
