import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from superapp.apps.whatsapp.models.phone_number import PhoneNumber

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PhoneNumber)
def fetch_templates_on_phone_number_save(sender, instance, created, **kwargs):
    """
    Signal handler to fetch templates when a phone number is saved
    """
    # Only fetch templates if:
    # 1. The phone number is using the official API
    # 2. It has the necessary credentials
    # 3. It's active
    if (instance.is_official_api() and
            instance.access_token and
            instance.business_account_id and
            instance.is_active):

        logger.info(f"Fetching templates for phone number {instance.id} ({instance.display_name})")

        try:
            templates = instance.fetch_templates()
            if templates:
                logger.info(f"Successfully fetched {len(templates)} templates for phone number {instance.id}")
            else:
                logger.warning(f"No templates fetched for phone number {instance.id}")
        except Exception as e:
            logger.error(f"Error fetching templates for phone number {instance.id}: {str(e)}")
