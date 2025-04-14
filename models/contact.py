from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


def validate_phone_number(value):
    """
    Validate that the phone number is in the correct international format.
    Should be country code + number without any symbols (e.g., 40777777777)
    """
    if not value.isdigit():
        raise ValidationError(_("Phone number must contain only digits"))
    
    # Check if it's a reasonable length for an international number (7-15 digits)
    if len(value) < 7 or len(value) > 15:
        raise ValidationError(_("Phone number must be between 7 and 15 digits"))
    
    # Ensure it starts with a country code (at least 1 digit)
    if len(value) < 3:
        raise ValidationError(_("Phone number must include country code"))


def normalize_phone_number(phone_number):
    """
    Normalize a phone number by removing any non-digit characters
    and ensuring it doesn't start with a plus sign.
    
    Args:
        phone_number (str): The phone number to normalize
        
    Returns:
        str: The normalized phone number
    """
    if not phone_number:
        return phone_number
        
    # Remove any non-digit characters
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    # If it starts with a plus sign in the original, we've already removed it
    return digits_only


class Contact(models.Model):
    """
    Model to store WhatsApp contacts
    """
    name = models.CharField(_("Name"), max_length=100)
    phone_number = models.CharField(
        _("Phone Number"), 
        max_length=15, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message=_("Phone number must contain only digits"),
            ),
            validate_phone_number,
        ],
        help_text=_("International format without '+' (e.g., 40777777777)")
    )
    whatsapp_chat_id = models.CharField(_("WhatsApp Chat ID"), max_length=100, blank=True, null=True,
                                      help_text=_("Used by WAHA API"))
    profile_picture_url = models.URLField(_("Profile Picture URL"), blank=True, null=True)
    is_business = models.BooleanField(_("Is Business"), default=False)
    is_verified = models.BooleanField(_("Is Verified"), default=False)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.phone_number})"
        
    def save(self, *args, **kwargs):
        # Normalize the phone number before saving
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)
    
    @classmethod
    def find_by_phone(cls, phone_number):
        """
        Find a contact by phone number, normalizing the input first.
        
        Args:
            phone_number (str): The phone number to search for
            
        Returns:
            Contact: The contact if found, None otherwise
        """
        normalized = normalize_phone_number(phone_number)
        try:
            return cls.objects.get(phone_number=normalized)
        except cls.DoesNotExist:
            return None
