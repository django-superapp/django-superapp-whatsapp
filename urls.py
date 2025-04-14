from django.urls import path

from superapp.apps.whatsapp.views.dashboard import dashboard
from superapp.apps.whatsapp.views.official_api_webhook import webhook
from superapp.apps.whatsapp.views.waha_webhook import waha_webhook


def extend_superapp_urlpatterns(main_urlpatterns):
    """
    Extend the main URL patterns with WhatsApp app specific URLs
    """
    main_urlpatterns += [
        path('api/whatsapp/webhook/<str:webhook_token>/', webhook, name='whatsapp_webhook'),
        path('api/whatsapp/webhook/waha/', waha_webhook, name='whatsapp_waha_webhook'),
        path('whatsapp/dashboard/', dashboard, name='whatsapp_dashboard'),
    ]
