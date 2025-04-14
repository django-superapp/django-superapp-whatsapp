import os

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


# Sample environment variables are available in .env.example


def extend_superapp_settings(main_settings):
    """
    Extend the main settings with WhatsApp app specific settings
    """
    main_settings['INSTALLED_APPS'] += ['superapp.apps.whatsapp']
    
    # WhatsApp API settings (these should be set in the environment or in the main settings)
    main_settings['WHATSAPP_API_VERSION'] = main_settings.get('WHATSAPP_API_VERSION', 'v22.0')
    main_settings['WHATSAPP_API_URL'] = main_settings.get(
        'WHATSAPP_API_URL', 
        f"https://graph.facebook.com/{main_settings['WHATSAPP_API_VERSION']}"
    )
    # Each phone number has its own verify_token for webhook verification
    
    # WhatsApp Embedded Signup settings
    main_settings['WHATSAPP_APP_ID'] = os.environ.get('WHATSAPP_APP_ID', main_settings.get('WHATSAPP_APP_ID', ''))
    main_settings['WHATSAPP_CONFIGURATION_ID'] = os.environ.get('WHATSAPP_CONFIGURATION_ID', main_settings.get('WHATSAPP_CONFIGURATION_ID', ''))
    
    # Add WhatsApp models to the Unfold admin navigation
    main_settings.setdefault('UNFOLD', {}).setdefault('SIDEBAR', {}).setdefault('navigation', [])
    main_settings['UNFOLD']['SIDEBAR']['navigation'].append({
        "title": _("WhatsApp"),
        "icon": "chat",
        "items": [
            {
                "title": lambda request: _("Phone Numbers"),
                "icon": "phone",
                "link": reverse_lazy("admin:whatsapp_phonenumber_changelist"),
                "permission": lambda request: request.user.has_perm("whatsapp.view_phonenumber"),
            },
            {
                "title": lambda request: _("Messages"),
                "icon": "message",
                "link": reverse_lazy("admin:whatsapp_message_changelist"),
                "permission": lambda request: request.user.has_perm("whatsapp.view_message"),
            },
            {
                "title": lambda request: _("Contacts"),
                "icon": "contacts",
                "link": reverse_lazy("admin:whatsapp_contact_changelist"),
                "permission": lambda request: request.user.has_perm("whatsapp.view_contact"),
            },
            {
                "title": lambda request: _("Templates"),
                "icon": "description",
                "link": reverse_lazy("admin:whatsapp_template_changelist"),
                "permission": lambda request: request.user.has_perm("whatsapp.view_template"),
            },
        ]
    })
