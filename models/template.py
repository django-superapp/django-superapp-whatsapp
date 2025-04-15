import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

from django.conf import settings

logger = logging.getLogger(__name__)

class Template(models.Model):
    """WhatsApp Message Template"""
    
    TEMPLATE_STATUS_CHOICES = (
        ('APPROVED', _('Approved')),
        ('PENDING', _('Pending')),
        ('REJECTED', _('Rejected')),
        ('PAUSED', _('Paused')),
        ('DISABLED', _('Disabled')),
    )
    
    TEMPLATE_CATEGORY_CHOICES = (
        ('AUTHENTICATION', _('Authentication')),
        ('MARKETING', _('Marketing')),
        ('UTILITY', _('Utility')),
    )

    phone_number = models.ForeignKey('whatsapp.PhoneNumber', on_delete=models.CASCADE, 
                                    related_name='templates',
                                    verbose_name=_('Phone Number'))
    
    # Template identification
    template_id = models.CharField(_('Template ID'), max_length=255, blank=True, null=True)
    name = models.CharField(_('Template Name'), max_length=255)
    language = models.CharField(_('Language'), max_length=10, default=settings.DEFAULT_LANGUAGE_CODE)
    
    # Template status and category
    status = models.CharField(_('Status'), max_length=20, choices=TEMPLATE_STATUS_CHOICES, default='PENDING')
    category = models.CharField(_('Category'), max_length=20, choices=TEMPLATE_CATEGORY_CHOICES, default='UTILITY')
    
    # Template content
    header_text = models.CharField(_('Header Text'), max_length=255, blank=True, null=True)
    header_type = models.CharField(_('Header Type'), max_length=20, blank=True, null=True,
                                 help_text=_('Type of header: TEXT, IMAGE, DOCUMENT, VIDEO'))
    
    body_text = models.TextField(_('Body Text'))
    footer_text = models.CharField(_('Footer Text'), max_length=255, blank=True, null=True)
    
    # Template components (stored as JSON)
    components = models.JSONField(_('Components'), blank=True, null=True,
                                help_text=_('JSON representation of template components'))
    
    # Template buttons (stored as JSON)
    buttons = models.JSONField(_('Buttons'), blank=True, null=True,
                             help_text=_('JSON representation of template buttons'))
    
    # Template examples (stored as JSON)
    examples = models.JSONField(_('Examples'), blank=True, null=True,
                              help_text=_('Example values for template variables'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('WhatsApp Template')
        verbose_name_plural = _('WhatsApp Templates')
        ordering = ['-created_at']
        unique_together = [['phone_number', 'name', 'language']]
    
    def __str__(self):
        return f"{self.name} ({self.language})"
    
    @property
    def is_approved(self):
        """Check if template is approved"""
        return self.status == 'APPROVED'
    
    @property
    def has_header(self):
        """Check if template has a header"""
        return bool(self.header_text or self.header_type)
    
    @property
    def has_footer(self):
        """Check if template has a footer"""
        return bool(self.footer_text)
    
    @property
    def has_buttons(self):
        """Check if template has buttons"""
        return bool(self.buttons)
        
    def get_required_variables(self):
        """
        Extract all required variables from the template components
        
        Returns:
            dict: A dictionary with keys 'body' and 'buttons' containing lists of required variables
        """
        required_vars = {
            'body': [],
            'buttons': []
        }
        
        if not self.components:
            return required_vars
            
        # Extract body variables
        for component in self.components:
            if not isinstance(component, dict):
                continue
                
            comp_type = component.get('type', '').lower()
            
            # Extract body text variables
            if comp_type == 'body' and 'example' in component:
                example = component.get('example', {})
                if 'body_text_named_params' in example:
                    for param in example.get('body_text_named_params', []):
                        if isinstance(param, dict) and 'param_name' in param:
                            required_vars['body'].append({
                                'name': param['param_name'],
                                'example': param.get('example', '')
                            })
            
            # Extract button variables
            elif comp_type == 'buttons':
                buttons = component.get('buttons', [])
                for i, button in enumerate(buttons):
                    if not isinstance(button, dict):
                        continue
                        
                    button_type = button.get('type', '').upper()
                    if button_type == 'URL' and 'url' in button and 'example' in button:
                        # Extract variables from URL format
                        url = button.get('url', '')
                        if '{{1}}' in url or '%7B%7B1%7D%7D' in url:
                            required_vars['buttons'].append({
                                'button_index': i,
                                'param_index': 1,
                                'example': button.get('example', [''])[0] if isinstance(button.get('example', []), list) else ''
                            })
        
        return required_vars
        
    def validate_variables(self, variables):
        """
        Validate if the provided variables match the required template variables
        
        Args:
            variables: Dictionary of variables to validate
            
        Returns:
            tuple: (is_valid, missing_variables)
        """
        if not variables:
            variables = {}
            
        required = self.get_required_variables()
        missing = {
            'body': [],
            'buttons': []
        }
        
        # Check body variables
        for var in required['body']:
            if var['name'] not in variables:
                missing['body'].append(var['name'])
                
        # Check button variables
        for button_var in required['buttons']:
            button_key = f"button_{button_var['button_index']}_param_{button_var['param_index']}"
            if button_key not in variables:
                missing['buttons'].append(button_key)
                
        is_valid = len(missing['body']) == 0 and len(missing['buttons']) == 0
        return is_valid, missing

    def get_absolute_url(self):
        return self.get_facebook_manager_url()

    def get_facebook_manager_url(self):
        """
        Generate URL to view/configure this template in Facebook Business Manager

        Returns:
            str: URL to the template in Facebook Business Manager or None if required IDs are missing
        """
        if not self.phone_number:
            return None

        business_id = self.phone_number.business_id
        waba_id = self.phone_number.waba_id

        if not business_id or not waba_id:
            # Fall back to business_account_id if waba_id is not set
            business_id = self.phone_number.business_account_id

            if not business_id:
                return None

        return (f"https://business.facebook.com/latest/whatsapp_manager/message_templates/"
                f"?business_id={business_id}&tab=message-templates&childRoute=CAPI"
                f"&id={self.template_id}&nav_ref=whatsapp_manager")

    @classmethod
    def from_api_response(cls, phone_number, template_data):
        """
        Create or update a Template instance from WhatsApp API response
        
        Args:
            phone_number: PhoneNumber instance
            template_data: Template data from WhatsApp API
            
        Returns:
            Template instance
        """
        # Safely extract values with proper type checking
        template_id = template_data.get('id') if isinstance(template_data, dict) else None
        name = template_data.get('name') if isinstance(template_data, dict) else str(template_data)
        
        # Default to PENDING if status is missing or invalid
        status = 'PENDING'
        if isinstance(template_data, dict) and 'status' in template_data:
            status_value = template_data['status']
            if isinstance(status_value, str):
                status = status_value.upper()
        
        # Default to UTILITY if category is missing or invalid
        category = 'UTILITY'
        if isinstance(template_data, dict) and 'category' in template_data:
            category_value = template_data['category']
            if isinstance(category_value, str):
                category = category_value.upper()
        
        # Get language from template data
        language = 'en'
        if isinstance(template_data, dict) and 'language' in template_data:
            language_data = template_data['language']
            if isinstance(language_data, dict) and 'code' in language_data:
                language = language_data['code']
        
        # Try to find existing template
        try:
            template = cls.objects.get(
                phone_number=phone_number,
                name=name,
                language=language
            )
        except cls.DoesNotExist:
            template = cls(
                phone_number=phone_number,
                name=name,
                language=language
            )
        
        # Update template fields
        template.template_id = template_id
        template.status = status
        template.category = category
        
        # Process components
        if isinstance(template_data, dict) and 'components' in template_data:
            components_data = template_data['components']
            if isinstance(components_data, list):
                template.components = components_data
                
                # Extract header, body, footer from components
                for component in components_data:
                    if not isinstance(component, dict):
                        continue
                        
                    comp_type = component.get('type', '')
                    if isinstance(comp_type, str):
                        comp_type = comp_type.lower()
                    else:
                        continue
                    
                    if comp_type == 'header':
                        template.header_type = component.get('format', 'TEXT')
                        if 'text' in component:
                            template.header_text = component['text']
                    
                    elif comp_type == 'body':
                        if 'text' in component:
                            template.body_text = component['text']
                    
                    elif comp_type == 'footer':
                        if 'text' in component:
                            template.footer_text = component['text']
                    
                    elif comp_type == 'buttons':
                        buttons = component.get('buttons', [])
                        if isinstance(buttons, list):
                            template.buttons = buttons
        
        # Process examples if available
        if isinstance(template_data, dict) and 'example' in template_data:
            template.examples = template_data['example']
        
        template.save()
        return template
