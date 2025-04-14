import unfold
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from superapp.apps.whatsapp.models import Message


@admin.register(Message, site=superapp_admin_site)
class MessageAdmin(SuperAppModelAdmin):
    list_display = ['id', 'direction', 'message_type', 'from_number', 'to_number', 'short_content', 'status', 'timestamp', 'created_at']
    list_filter = ['direction', 'message_type', 'status', 'phone_number', 'timestamp', 'created_at', 'updated_at']
    search_fields = ['from_number', 'to_number', 'content', 'message_id', 'error_code', 'error_message']
    autocomplete_fields = ['phone_number', 'contact', 'template']
    readonly_fields = ['message_id', 'from_number', 'direction', 'media_preview', 'media_id', 'media_mime_type', 
                      'timestamp', 'status', 'delivered_at', 'read_at', 'error_code', 'error_message', 
                      'created_at', 'updated_at']
    actions = ['retry_sending_messages']
    actions_detail = ['retry_send_message']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize form fields for foreign keys"""
        if db_field.name == "phone_number":
            kwargs["required"] = True
            kwargs["help_text"] = _("WhatsApp account to send from")
        
        if db_field.name == "contact":
            kwargs["required"] = True
            kwargs["help_text"] = _("Select a contact to send the message to")
            # The ChainedForeignKey will handle filtering based on phone_number
        
        if db_field.name == "template":
            kwargs["required"] = False
            kwargs["help_text"] = _("Select a template to use for this message")
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize form fields for JSON fields"""
        if db_field.name == "template_variables":
            kwargs["required"] = False
            
            # Get template ID from request if available
            template_id = None
            if request.method == 'GET' and 'template' in request.GET:
                template_id = request.GET.get('template')
            elif request.method == 'POST' and 'template' in request.POST:
                template_id = request.POST.get('template')
                
            # If we have a template ID, get the sample variables
            if template_id:
                try:
                    from superapp.apps.whatsapp.models import Template
                    template = Template.objects.get(id=template_id)
                    sample = template.sample_variables
                    if sample:
                        import json
                        kwargs["help_text"] = _("JSON object with template variables. Example: %(example)s") % {
                            'example': json.dumps(sample, indent=2, ensure_ascii=False)
                        }
                        return super().formfield_for_dbfield(db_field, request, **kwargs)
                except Exception:
                    pass
                    
            # Default help text if no template or error
            kwargs["help_text"] = _("JSON object with template variables. Example: {'client_name': 'John Doe', 'client_phone': '123456789', 'button_0_param_1': '123456'}")
            
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    add_fieldsets = (
        (_('Contact Information'), {
            'fields': ('phone_number', 'contact')
        }),
        (_('Message Details'), {
            'fields': ('message_type', 'content', 'media_file')
        }),
        (_('Template Information'), {
            'fields': ('template', 'template_variables'),
            'classes': ('collapse',),
            'description': _('For template messages, select a template and provide the required variables')
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for add and change views"""
        if not obj:
            return self.add_fieldsets
        
        return (
            (_('Message Details'), {
                'fields': ('message_id', 'conversation_id', 'direction', 'message_type', 'status', 'timestamp')
            }),
            (_('Contact Information'), {
                'fields': ('phone_number', 'contact', 'from_number', 'to_number')
            }),
            (_('Content'), {
                'fields': ('content', 'media_preview', 'media_id', 'media_type', 'media_mime_type', 'content_type')
            }),
            (_('Template Information'), {
                'fields': ('template', 'template_variables'),
                'classes': ('collapse',),
                'description': _('Template information and variables')
            }),
            (_('Status Information'), {
                'fields': ('delivered_at', 'read_at', 'error_code', 'error_message'),
                'classes': ('collapse',),
                'description': _('Detailed status information')
            }),
            (_('Metadata'), {
                'fields': ('metadata', 'raw_message'),
                'classes': ('collapse',),
                'description': _('Technical metadata and raw message data')
            }),
            (_('Timestamps'), {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
                'description': _('System timestamps')
            }),
        )
    
    def get_readonly_fields(self, request, obj=None):
        """Make most fields readonly for existing messages, but editable for new ones"""
        if obj:  # Editing an existing object
            return self.readonly_fields
        return ['message_id', 'from_number', 'direction', 'status', 'timestamp', 
                'delivered_at', 'read_at', 'error_code', 'error_message', 
                'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        """Custom save method for Message model"""
        if not change:  # Only for new objects
            # Set fixed values for outgoing messages
            obj.direction = 'outgoing'
            obj.status = 'pending'
            
            # Set from_number from the phone_number
            if obj.phone_number:
                obj.from_number = obj.phone_number.phone_number
            
            # Set to_number from the contact
            if obj.contact:
                obj.to_number = obj.contact.phone_number
            else:
                raise ValueError("Contact is required for outgoing messages")
            
            # Generate a temporary message_id if not provided
            if not obj.message_id:
                import uuid
                obj.message_id = f"temp_{uuid.uuid4()}"

        super().save_model(request, obj, form, change)
    
    def short_content(self, obj):
        """Display a shortened version of the content in list view"""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    short_content.short_description = _('Content')
    
    def media_preview(self, obj):
        """Display a preview of media content if available"""
        if not obj.media_file:
            return '-'
        
        file_url = obj.media_file.url
        
        # Handle different media types
        if obj.message_type == 'image':
            return format_html('<img src="{}" style="max-width:300px; max-height:300px" />', file_url)
        elif obj.message_type == 'video':
            return format_html('''
                <video width="320" height="240" controls>
                    <source src="{}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            ''', file_url)
        elif obj.message_type == 'audio':
            return format_html('''
                <audio controls>
                    <source src="{}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            ''', file_url)
        elif obj.message_type == 'document':
            filename = obj.media_file.name.split('/')[-1]
            return format_html('<a href="{}" target="_blank">{}</a>', file_url, filename)
        else:
            return format_html('<a href="{}" target="_blank">View media</a>', file_url)
    
    media_preview.short_description = _('Media')
    media_preview.allow_tags = True

    def has_add_permission(self, request):
        """Allow adding outgoing messages through admin"""
        return True

    @unfold.decorators.action(description=_("Retry sending selected messages"))
    def retry_sending_messages(self, request, queryset):
        """Admin action to retry sending failed or pending messages"""
        success_count = 0
        error_count = 0
        error_messages = []
        
        for msg in queryset:
            if msg.direction != 'outgoing':
                error_count += 1
                continue
                
            try:
                result = msg.retry_send()
                if result:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                error_messages.append(f"Error for message {msg.id}: {str(e)}")
        
        if success_count > 0:
            self.message_user(
                request, 
                _("Successfully retried sending %(count)d messages.") % {'count': success_count},
                messages.SUCCESS
            )
        
        if error_count > 0:
            error_text = _("Failed to retry %(count)d messages.") % {'count': error_count}
            if error_messages:
                error_text += " " + " ".join(error_messages[:5])
                if len(error_messages) > 5:
                    error_text += f" (and {len(error_messages) - 5} more errors)"
            
            self.message_user(request, error_text, messages.ERROR)

        return redirect(
            reverse_lazy('admin:whatsapp_message_changelist')
        )

    @unfold.decorators.action(description=_("Retry sending this message"))
    def retry_send_message(self, request, object_id):
        obj = Message.objects.get(id=object_id)
        """Row-level action to retry sending a failed or pending message"""
        if obj.direction != 'outgoing':
            self.message_user(
                request,
                _("Cannot retry sending an incoming message."),
                messages.ERROR
            )
            return
            
        try:
            result = obj.retry_send()
            if result:
                self.message_user(
                    request,
                    _("Successfully retried sending message #%(id)d.") % {'id': obj.id},
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    _("Failed to retry sending message #%(id)d.") % {'id': obj.id},
                    messages.ERROR
                )
        except Exception as e:
            self.message_user(
                request,
                _("Error retrying message #%(id)d: %(error)s") % {'id': obj.id, 'error': str(e)},
                messages.ERROR
            )
            raise e
        return redirect(
            reverse_lazy('admin:whatsapp_message_change', args=[object_id])
        )
