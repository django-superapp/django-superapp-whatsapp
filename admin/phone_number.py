from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.decorators import action

from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from superapp.apps.whatsapp.models import PhoneNumber


@admin.register(PhoneNumber, site=superapp_admin_site)
class PhoneNumberAdmin(SuperAppModelAdmin):
    list_display = ['display_name', 'phone_number', 'api_type', 'phone_number_id', 'is_active', 'is_configured', 'created_at']
    search_fields = ['display_name', 'phone_number', 'phone_number_id']
    list_filter = ['api_type', 'is_active', 'is_configured', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'whatsapp_signup_button', 'configure_waha_webhook_button', 'verify_token_display', 'fetch_templates_button']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('whatsapp-signup/', self.admin_site.admin_view(self.whatsapp_signup_view), name='whatsapp_signup'),
            path('configure-waha-webhook/<int:phone_number_id>/', self.admin_site.admin_view(self.configure_waha_webhook_view), name='configure_waha_webhook'),
            path('fetch-templates/<int:phone_number_id>/', self.admin_site.admin_view(self.fetch_templates_view), name='fetch_templates'),
        ]
        return custom_urls + urls

    def whatsapp_signup_button(self, obj):
        """Display a button to launch WhatsApp embedded signup"""
        return mark_safe(
            f'<a href="{reverse("admin:whatsapp_signup")}" '
            f'class="button bg-[#25D366] hover:bg-[#128C7E] text-white dark:text-white">'
            f'{_("Connect WhatsApp Business Account")}</a>'
        )
    whatsapp_signup_button.short_description = _("WhatsApp Integration")
    
    def configure_waha_webhook_button(self, obj):
        """Display a button to configure WAHA webhook"""
        if obj and obj.is_waha_api():
            return mark_safe(
                f'<a href="{reverse("admin:configure_waha_webhook", args=[obj.pk])}" '
                f'class="button bg-[#25D366] hover:bg-[#128C7E] text-white dark:text-white px-4 py-2 rounded">'
                f'{_("Set Up Message Notifications")}</a>'
            )
        return ""
    configure_waha_webhook_button.short_description = _("WAHA Webhook")
    
    def fetch_templates_button(self, obj):
        """Display a button to fetch templates from WhatsApp API"""
        if obj and obj.is_official_api():
            return mark_safe(
                f'<a href="{reverse("admin:fetch_templates", args=[obj.pk])}" '
                f'class="button bg-[#25D366] hover:bg-[#128C7E] text-white dark:text-white px-4 py-2 rounded">'
                f'{_("Fetch Message Templates")}</a>'
            )
        return ""
    fetch_templates_button.short_description = _("Message Templates")

    def configuration_status(self, obj):
        """Display configuration status as a colored indicator"""
        if obj.is_configured:
            return format_html('<span class="text-green-600 dark:text-green-400">✓ Complete</span>')
        else:
            return format_html('<span class="text-red-600 dark:text-red-400">✗ Not Configured</span>')
    configuration_status.short_description = _("Configuration")

    def get_fieldsets(self, request, obj=None):
        """Override to pass request to fieldsets for URL building"""
        fieldsets = [
            (None, {
                'fields': ('display_name', 'phone_number', 'api_type', 'is_active', 'is_configured')
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        ]

        # Add API-specific fieldsets based on the API type
        if obj is None or obj.is_official_api():
            fieldsets.insert(1, ('Official WhatsApp Business API', {
                'fields': ('phone_number_id', 'business_account_id', 'access_token'),
                'description': _('Configure the official WhatsApp Business API credentials')
            }))

        if obj is None or obj.is_waha_api():
            fieldsets.insert(1, ('WAHA API Configuration', {
                'fields': ('waha_endpoint', 'waha_username', 'waha_password', 'waha_session'),
                'description': _('Configure the WAHA API credentials')
            }))
            
        # Add the WhatsApp integration button for new objects or when editing
        if obj is not None:
            if obj.is_official_api():
                fieldsets.insert(1, ('WhatsApp Integration', {
                    'fields': ('whatsapp_signup_button',),
                    'description': _('Connect your WhatsApp Business account')
                }))

        # Add a Configuration Checklist fieldset if the object exists
        if obj is not None:
            # Create API-specific configuration instructions
            if obj.is_official_api():
                config_description = format_html(
                    '<div class="help p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">'
                    '<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Official WhatsApp Business API Configuration</h3>'
                    '<ol class="space-y-6 list-decimal">'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">1. Create Access Token and Test Number:</strong>'
                    '<p class="mb-2 dark:text-gray-300">Create a permanent System User access token following these steps:</p>'
                    '<ul class="list-disc pl-5 space-y-2 dark:text-gray-300">'
                    '<li>Go to <a href="https://business.facebook.com/settings/system-users" target="_blank" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline">Business Settings > System Users</a></li>'
                    '<li>Click <strong>+ Add</strong> to create a new system user with <strong>Admin</strong> role</li>'
                    '<li>Click on the system user name, then <strong>Assign Assets</strong></li>'
                    '<li>Select your app and grant <strong>Manage app</strong> permission</li>'
                    '<li>Click <strong>Generate token</strong>, select your app, and add these permissions: <strong>business_management</strong>, <strong>whatsapp_business_management</strong>, and <strong>whatsapp_business_messaging</strong></li>'
                    '<li>Copy the generated token and paste it in the <strong>Access Token</strong> field above</li>'
                    '</ul>'
                    '<p class="mb-2 mt-3 dark:text-gray-300">Then go to the <a href="https://developers.facebook.com/apps/1326136408459845/whatsapp-business/wa-dev-console" target="_blank" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline">WhatsApp Developer Console</a> to:</p>'
                    '<ul class="list-disc pl-5 space-y-2 dark:text-gray-300">'
                    '<li>Send a test message to verify your setup</li>'
                    '<li>Copy your WhatsApp phone number ID and business account ID</li>'
                    '<li>Enter these values in the fields above</li>'
                    '</ul>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">2. Configure Webhook:</strong>'
                    '<p class="mb-2 dark:text-gray-300">Go to <a href="https://developers.facebook.com/apps/1326136408459845/webhooks/" target="_blank" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline">Webhooks Configuration</a> and:</p>'
                    '<ul class="list-disc pl-5 space-y-2 dark:text-gray-300">'
                    '<li>Add a new webhook subscription for <strong>WhatsApp Business Account</strong> product</li>'
                    '<li>Enter the callback URL below</li>'
                    '<li>Set up the verify token shown below</li>'
                    '<li>Select API version <strong>v22.0</strong> from the dropdown</li>'
                    '<li>Subscribe to these fields: <strong>messages</strong>, <strong>message_template_status_update</strong>, <strong>message_template_quality_update</strong>, and <strong>message_template_components_update</strong></li>'
                    '<li>Make sure to check all these fields in the subscription dialog to receive template updates</li>'
                    '</ul>'
                    '<p class="dark:text-gray-300 mt-2">Use this callback URL:</p>'
                    '<code class="block p-2 mt-2 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">{}/{}</code>'
                    '<p class="dark:text-gray-300 mt-3">Use this verify token:</p>'
                    '<code class="block p-2 mt-2 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">{}</code>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">3. Verify API Connection:</strong>'
                    '<p class="dark:text-gray-300">Send another test message through the Developer Console to verify your webhook is receiving events.</p>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">4. Register Message Templates:</strong>'
                    '<p class="dark:text-gray-300">Create and register message templates in your Meta Business account for sending notifications.</p>'
                    '</div>'
                    '</ol>'
                    '<p class="mt-4 text-sm text-gray-600 dark:text-gray-400">Check when you\'ve completed all configuration steps.</p>'
                    '</div>',
                    request.build_absolute_uri('/api/whatsapp/webhook'),
                    obj.webhook_token + "/",
                    obj.verify_token
                )
            elif obj.is_waha_api():
                webhook_button = self.configure_waha_webhook_button(obj)
                config_description = format_html(
                    '<div class="help p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">'
                    '<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">WAHA API Configuration</h3>'
                    '<ol class="space-y-6 list-decimal">'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">1. Set Up WAHA Server:</strong>'
                    '<p class="dark:text-gray-300">Ensure your WAHA server is running and accessible at the endpoint URL you provided.</p>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">2. Initialize WhatsApp Session:</strong>'
                    '<p class="dark:text-gray-300">Start a new session on your WAHA server and scan the QR code with your WhatsApp phone.</p>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">3. Configure Webhook Events:</strong>'
                    '<p class="dark:text-gray-300">Set up webhook events to receive notifications from WhatsApp.</p>'
                    '<div class="mt-3">{}</div>'
                    '</div>'
                    '<div class="p-3 bg-white dark:bg-gray-700 rounded border border-gray-100 dark:border-gray-600">'
                    '<strong class="block text-gray-700 dark:text-gray-300 mb-2">4. Test Connection:</strong>'
                    '<p class="dark:text-gray-300">Send a test message to verify your WAHA integration is working properly.</p>'
                    '</div>'
                    '</ol>'
                    '<p class="mt-4 text-sm text-gray-600 dark:text-gray-400">Note: WAHA API uses an unofficial WhatsApp Web client and may have limitations.</p>'
                    '</div>',
                    webhook_button
                )
            else:
                config_description = format_html(
                    '<div class="help p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">'
                    '<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">WhatsApp Configuration Instructions</h3>'
                    '<p class="dark:text-gray-300">Please select an API type to see specific configuration instructions.</p>'
                    '</div>'
                )
                
            # Add the configuration checklist fieldset
            if obj.is_waha_api():
                fieldsets.append((_('Configuration Checklist'), {
                    'fields': ('is_configured',),
                    'description': config_description,
                }))
            else:
                fieldsets.append((_('Configuration Checklist'), {
                    'fields': ('is_configured',),
                    'description': config_description,
                    'classes': ('collapse',)
                }))
                
            # Add the templates section for official API
            if obj.is_official_api():
                fieldsets.append((_('Message Templates'), {
                    'fields': ('fetch_templates_button',),
                    'description': _('Manage message templates for this WhatsApp phone number. '
                                   'Templates allow you to send structured messages to your customers.')
                }))

        return fieldsets

    def whatsapp_signup_view(self, request):
        """View for WhatsApp embedded signup"""
        # Get app settings from environment or settings
        app_id = getattr(settings, 'WHATSAPP_APP_ID', '')
        graph_api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v17.0')
        configuration_id = getattr(settings, 'WHATSAPP_CONFIGURATION_ID', '')

        context = {
            'title': _('WhatsApp Business Account Signup'),
            'app_id': app_id,
            'graph_api_version': graph_api_version,
            'configuration_id': configuration_id,
            **self.admin_site.each_context(request),
        }

        return TemplateResponse(request, 'admin/whatsapp/phonenumber/whatsapp_signup.html', context)
        
    @action(
        description=_("Fetch Templates"),
        icon="download",
        permissions=["change"]
    )
    def action_fetch_templates(self, request, queryset):
        """Action to fetch templates for selected phone numbers"""
        from django.contrib import messages
        
        success_count = 0
        error_count = 0
        
        for phone_number in queryset:
            if not phone_number.is_official_api():
                error_count += 1
                continue
                
            templates = phone_number.fetch_templates()
            
            if templates:
                success_count += 1
                messages.success(
                    request, 
                    _("Successfully imported %(count)d templates for %(phone)s") % {
                        'count': len(templates),
                        'phone': phone_number.display_name
                    }
                )
            else:
                error_count += 1
                messages.error(
                    request,
                    _("Failed to fetch templates for %(phone)s") % {'phone': phone_number.display_name}
                )
        
        if success_count > 0 and error_count == 0:
            return _("Successfully fetched templates for all selected phone numbers")
        elif success_count > 0 and error_count > 0:
            return _("Fetched templates for some phone numbers, but encountered errors with others")
        else:
            return _("Failed to fetch templates. Make sure you've selected phone numbers using the official WhatsApp API")
    
    def fetch_templates_view(self, request, phone_number_id):
        """View for fetching templates from WhatsApp API"""
        from django.contrib import messages
        
        try:
            phone_number = PhoneNumber.objects.get(pk=phone_number_id)
        except PhoneNumber.DoesNotExist:
            messages.error(request, _("Phone number not found"))
            return redirect('admin:whatsapp_phonenumber_changelist')
            
        if not phone_number.is_official_api():
            messages.error(request, _("Templates can only be fetched for phone numbers using the official WhatsApp API"))
            return redirect('admin:whatsapp_phonenumber_change', phone_number_id)
            
        templates = phone_number.fetch_templates()
        
        if templates:
            messages.success(
                request, 
                _("Successfully imported %(count)d templates") % {'count': len(templates)}
            )
        else:
            messages.error(request, _("Failed to fetch templates. Check the phone number configuration and try again."))
            
        return redirect('admin:whatsapp_phonenumber_change', phone_number_id)
    
    def configure_waha_webhook_view(self, request, phone_number_id):
        """View for configuring WAHA webhook events"""
        from django.contrib import messages
        from superapp.apps.whatsapp.services import WAHAService
        
        try:
            phone_number = PhoneNumber.objects.get(pk=phone_number_id, api_type='waha')
        except PhoneNumber.DoesNotExist:
            messages.error(request, _("Phone number not found or not using WAHA API"))
            return redirect('admin:whatsapp_phonenumber_changelist')
            
        # Define available events
        available_events = [
            ('message', _('Incoming Messages')),
        ]
        
        # Handle form submission
        if request.method == 'POST':
            selected_events = request.POST.getlist('events')
            webhook_url = request.POST.get('webhook_url')
            
            if not webhook_url:
                messages.error(request, _("Webhook URL is required"))
            elif not selected_events:
                messages.error(request, _("At least one event must be selected"))
            else:
                try:
                    # Create WAHA service
                    waha_service = WAHAService(
                        endpoint=phone_number.waha_endpoint,
                        username=phone_number.waha_username,
                        password=phone_number.waha_password,
                        session=phone_number.waha_session
                    )
                    
                    # Configure webhook
                    result = waha_service.configure_webhooks(webhook_url, selected_events)
                    
                    # Check if the response contains an error
                    if result.get('error'):
                        error_msg = result.get('error')
                        messages.error(request, _("Failed to configure webhook: %s") % error_msg)
                    else:
                        # Session update was successful
                        messages.success(request, _("Webhook configured successfully"))
                        
                        # Mark the phone number as configured if it's not already
                        if not phone_number.is_configured:
                            phone_number.is_configured = True
                            phone_number.save(update_fields=['is_configured'])
                        
                except Exception as e:
                    messages.error(request, _("Error configuring webhook: %s") % str(e))
                
                return redirect('admin:whatsapp_phonenumber_change', phone_number_id)
        
        # Prepare webhook URL
        webhook_url = request.build_absolute_uri('/api/whatsapp/webhook/waha/')
        
        context = {
            'title': _('Configure WAHA Webhook'),
            'phone_number': phone_number,
            'available_events': available_events,
            'webhook_url': webhook_url,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }
        
        return TemplateResponse(request, 'admin/whatsapp/phonenumber/configure_waha_webhook.html', context)
    
    def verify_token_display(self, obj):
        """Display the verify token for webhook configuration"""
        if not obj or not obj.verify_token:
            return ""
            
        return format_html(
            '<div class="p-2 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">'
            '{}'
            '</div>',
            obj.verify_token
        )
    verify_token_display.short_description = _("Webhook Verify Token")
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for API type field
        if 'api_type' in form.base_fields:
            form.base_fields['api_type'].help_text = _(
                'Select the API type to use for this phone number. '
                'The official WhatsApp Business API requires a Meta Business account. '
                'WAHA API is an unofficial API that uses WhatsApp Web.'
            )
            
        return form
