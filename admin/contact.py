from django.contrib import admin
from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from superapp.apps.whatsapp.models import Contact


@admin.register(Contact, site=superapp_admin_site)
class ContactAdmin(SuperAppModelAdmin):
    list_display = ['name', 'phone_number', 'whatsapp_chat_id', 'is_business', 'is_verified', 'created_at', 'updated_at']
    search_fields = ['name', 'phone_number', 'whatsapp_chat_id']
    list_filter = ['is_business', 'is_verified', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'phone_number', 'whatsapp_chat_id')
        }),
        ('Profile', {
            'fields': ('profile_picture_url', 'is_business', 'is_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
