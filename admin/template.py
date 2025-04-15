import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from superapp.apps.whatsapp.models import Template
from django.conf import settings

@admin.register(Template, site=superapp_admin_site)
class TemplateAdmin(SuperAppModelAdmin):
    list_display = ['name', 'language', 'category', 'status_badge', 'phone_number', 'created_at']
    list_filter = ['status', 'category', 'language', 'phone_number', 'created_at']
    search_fields = ['name', 'body_text', 'header_text', 'footer_text']
    readonly_fields = [
        'template_id', 'status', 'created_at', 'updated_at',
        'template_preview', 'components_display', 'buttons_display',
        'sample_variables_display',
    ]
    fieldsets = [
        (None, {
            'fields': ('phone_number', 'name', 'language', 'category', 'status', 'template_id')
        }),
        (_('Template Content'), {
            'fields': ('header_type', 'header_text', 'body_text', 'footer_text')
        }),
        (_('Template Preview'), {
            'fields': ('template_preview',)
        }),
        (_('Template Variables'), {
            'fields': ('sample_variables_display',),
            'description': _('Sample variables to use when sending this template via the WhatsApp API')
        }),
        (_('Advanced'), {
            'fields': ('components_display', 'buttons_display',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    ]

    def status_badge(self, obj):
        """Display status as a colored badge"""
        status_colors = {
            'APPROVED': 'green',
            'PENDING': 'yellow',
            'REJECTED': 'red',
            'PAUSED': 'gray',
            'DISABLED': 'gray',
        }
        color = status_colors.get(obj.status, 'gray')

        return format_html(
            '<span class="px-2 py-1 text-xs font-medium rounded-full bg-{}-100 text-{}-800 dark:bg-{}-900 dark:text-{}-200">{}</span>',
            color, color, color, color, obj.status
        )
    status_badge.short_description = _('Status')

    def template_preview(self, obj):
        """Display a preview of the template"""
        preview_html = '<div class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">'

        # Header
        if obj.has_header:
            preview_html += '<div class="mb-3 font-semibold">'
            if obj.header_type == 'TEXT':
                preview_html += f'<div>{obj.header_text}</div>'
            else:
                preview_html += f'<div>[{obj.header_type}]</div>'
            preview_html += '</div>'

        # Body
        preview_html += f'<div class="mb-3 whitespace-pre-wrap">{obj.body_text}</div>'

        # Footer
        if obj.has_footer:
            preview_html += f'<div class="text-sm text-gray-500 dark:text-gray-400 mt-2">{obj.footer_text}</div>'

        # Buttons
        if obj.has_buttons and obj.buttons:
            preview_html += '<div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">'

            try:
                buttons = obj.buttons if isinstance(obj.buttons, list) else []
                for button in buttons:
                    btn_type = button.get('type', '')
                    if btn_type == 'QUICK_REPLY':
                        preview_html += f'<button class="mr-2 mb-2 px-3 py-1 bg-gray-200 dark:bg-gray-700 rounded-md text-sm">{button.get("text", "Button")}</button>'
                    elif btn_type == 'URL':
                        preview_html += f'<button class="mr-2 mb-2 px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-md text-sm">{button.get("text", "URL")}</button>'
                    elif btn_type == 'PHONE_NUMBER':
                        preview_html += f'<button class="mr-2 mb-2 px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 rounded-md text-sm">{button.get("text", "Call")}</button>'
            except Exception:
                preview_html += '<div class="text-red-500">Error parsing buttons</div>'

            preview_html += '</div>'

        preview_html += '</div>'
        return format_html(preview_html)
    template_preview.short_description = _('Template Preview')

    def components_display(self, obj):
        """Display components as formatted JSON"""
        if not obj.components:
            return '-'

        import json
        try:
            formatted_json = json.dumps(obj.components, indent=2)
            return format_html(
                '<pre class="p-2 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">{}</pre>',
                formatted_json
            )
        except Exception:
            return '-'
    components_display.short_description = _('Components JSON')

    def buttons_display(self, obj):
        """Display buttons as formatted JSON"""
        if not obj.buttons:
            return '-'

        import json
        try:
            formatted_json = json.dumps(obj.buttons, indent=2)
            return format_html(
                '<pre class="p-2 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">{}</pre>',
                formatted_json
            )
        except Exception:
            return '-'
    buttons_display.short_description = _('Buttons JSON')
    
    def sample_variables_display(self, obj):
        """
        Display sample variables in WhatsApp API format as documented in:
        https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates/
        
        Transforms template components into the format needed for API calls
        """
        if not obj.components:
            return mark_safe(str(_('No variables required for this template')))
        
        # Initialize the components array for the WhatsApp API format
        components_params = []
        
        # Process each component from the template
        for component in obj.components:
            if not isinstance(component, dict):
                continue
                
            comp_type = component.get('type', '').upper()
            
            # Process HEADER component
            if comp_type == 'HEADER':
                header_format = component.get('format', '').upper()
                if header_format and header_format != 'TEXT':
                    api_header = {
                        "type": "header",
                        "parameters": [
                            {
                                "type": header_format.lower()
                            }
                        ]
                    }
                    
                    # Add appropriate media object based on header type
                    if header_format == 'IMAGE':
                        api_header["parameters"][0]["image"] = {"link": "https://example.com/image.jpg"}
                    elif header_format == 'DOCUMENT':
                        api_header["parameters"][0]["document"] = {"link": "https://example.com/document.pdf"}
                    elif header_format == 'VIDEO':
                        api_header["parameters"][0]["video"] = {"link": "https://example.com/video.mp4"}
                    
                    components_params.append(api_header)
            
            # Process BODY component
            elif comp_type == 'BODY':
                body_text = component.get('text', '')
                example = component.get('example', {})
                
                # Check for named parameters
                if isinstance(example, dict) and 'body_text_named_params' in example and isinstance(example['body_text_named_params'], list):
                    body_params = []
                    
                    for param in example['body_text_named_params']:
                        if isinstance(param, dict) and 'param_name' in param and 'example' in param:
                            body_params.append({
                                "type": "text",
                                "parameter_name": param['param_name'],
                                "text": param['example']
                            })
                    
                    if body_params:
                        components_params.append({
                            "type": "body",
                            "parameters": body_params
                        })
                
                # Check for positional parameters if no named parameters
                elif '{{' in body_text:
                    import re
                    positional_pattern = r'\{\{(\d+)\}\}'
                    matches = re.findall(positional_pattern, body_text)
                    
                    if matches:
                        body_params = []
                        for match in matches:
                            body_params.append({
                                "type": "text",
                                "text": "SAMPLE_VALUE"
                            })
                        
                        if body_params:
                            components_params.append({
                                "type": "body",
                                "parameters": body_params
                            })
            
            # Process BUTTONS component
            elif comp_type == 'BUTTONS' and 'buttons' in component:
                buttons = component.get('buttons', [])
                
                if not isinstance(buttons, list):
                    continue
                
                for i, button in enumerate(buttons):
                    if not isinstance(button, dict):
                        continue
                    
                    button_type = button.get('type', '').upper()
                    
                    # Handle URL buttons with variables
                    if button_type == 'URL':
                        url = button.get('url', '')
                        examples = button.get('example', [])
                        
                        if '{{' in url and isinstance(examples, list) and examples:
                            components_params.append({
                                "type": "button",
                                "sub_type": "url",
                                "index": str(i),
                                "parameters": [
                                    {
                                        "type": "text",
                                        "text": examples[0] if examples else "BUTTON_URL_VALUE"
                                    }
                                ]
                            })
        
        if not components_params:
            return mark_safe(str(_('No variables required for this template')))

        c = {
            "language": {"code": settings.DEFAULT_LANGUAGE_CODE},
            "components": components_params,
        }
        # Format the JSON for display
        formatted_json = json.dumps(c, indent=2, ensure_ascii=False)
        
        return format_html(
            '<div class="mb-2 text-sm text-gray-600 dark:text-gray-400">{}</div>'
            '<pre class="p-3 bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-300 rounded text-sm overflow-auto">{}</pre>',
            _('Template variables (copy this for API calls):'),
            mark_safe(formatted_json)
        )
    sample_variables_display.short_description = _('Sample Variables')

