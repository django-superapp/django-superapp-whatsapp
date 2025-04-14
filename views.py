from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
import json
import logging
from superapp.apps.whatsapp.models import PhoneNumber, Message, Contact

logger = logging.getLogger(__name__)

@csrf_exempt
def webhook(request):
    """
    WhatsApp Webhook endpoint to receive messages and events
    """
    if request.method == 'GET':
        # Handle webhook verification from Meta
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        verify_token = getattr(settings, 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'default_verify_token')
        
        if mode == 'subscribe' and token == verify_token:
            return HttpResponse(challenge)
        else:
            logger.warning(f"Webhook verification failed: {mode}, {token}")
            return HttpResponse('Verification failed', status=403)
    
    elif request.method == 'POST':
        # Handle incoming messages and status updates
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Received webhook data: {data}")
            
            # Process the webhook data
            if 'object' in data and data['object'] == 'whatsapp_business_account':
                process_webhook_event(data)
                return HttpResponse('Webhook processed')
            else:
                logger.warning(f"Received unknown webhook object: {data.get('object')}")
                return HttpResponse('Unknown webhook object', status=400)
                
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return HttpResponse('Error processing webhook', status=500)
    
    return HttpResponse('Method not allowed', status=405)

def process_webhook_event(data):
    """
    Process webhook events from WhatsApp Business API
    """
    try:
        # Process each entry in the webhook
        for entry in data.get('entry', []):
            # Process each change in the entry
            for change in entry.get('changes', []):
                if change.get('field') == 'messages':
                    value = change.get('value', {})
                    
                    # Get the phone number
                    phone_number_id = value.get('metadata', {}).get('phone_number_id')
                    try:
                        phone_number = PhoneNumber.objects.get(phone_number_id=phone_number_id)
                    except PhoneNumber.DoesNotExist:
                        logger.error(f"Phone number with ID {phone_number_id} not found")
                        continue
                    
                    # Process messages
                    for message_data in value.get('messages', []):
                        process_incoming_message(phone_number, message_data)
                    
                    # Process message status updates
                    for status_data in value.get('statuses', []):
                        process_message_status(status_data)
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")
        raise

def process_incoming_message(phone_number, message_data):
    """
    Process an incoming message from WhatsApp
    """
    try:
        message_id = message_data.get('id')
        from_number = message_data.get('from')
        timestamp = timezone.datetime.fromtimestamp(int(message_data.get('timestamp')))
        
        # Get or create contact
        contact, created = Contact.objects.get_or_create(
            phone_number=from_number,
            defaults={'name': from_number}  # Use phone number as name initially
        )
        
        # If this is a WAHA API phone number, update the chat_id
        if phone_number.is_waha_api() and not contact.whatsapp_chat_id:
            contact.whatsapp_chat_id = from_number
            contact.save(update_fields=['whatsapp_chat_id'])
        
        # Determine message type and content
        message_type = message_data.get('type')
        content = ''
        media_url = None
        media_id = None
        
        if message_type == 'text':
            content = message_data.get('text', {}).get('body', '')
        elif message_type in ['image', 'audio', 'video', 'document']:
            media_data = message_data.get(message_type, {})
            media_id = media_data.get('id')
            # Note: To get the actual media URL, you would need to make an API call
            # using the media_id to download the media
            content = f"{message_type.capitalize()} message"
        elif message_type == 'location':
            location = message_data.get('location', {})
            content = json.dumps(location)
        elif message_type == 'button':
            content = message_data.get('button', {}).get('text', '')
        elif message_type == 'interactive':
            interactive = message_data.get('interactive', {})
            content = json.dumps(interactive)
        
        # Create the message
        Message.objects.create(
            phone_number=phone_number,
            contact=contact,
            message_id=message_id,
            from_number=from_number,
            to_number=phone_number.phone_number,
            direction='incoming',
            message_type=message_type,
            content=content,
            media_url=media_url,
            media_id=media_id,
            timestamp=timestamp,
            status='received'
        )
        
        logger.info(f"Processed incoming {message_type} message {message_id} from {from_number}")
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        raise

def process_message_status(status_data):
    """
    Process a message status update from WhatsApp
    """
    try:
        message_id = status_data.get('id')
        status = status_data.get('status')
        
        # Map WhatsApp status to our status
        status_mapping = {
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed'
        }
        
        # Update the message status
        try:
            message = Message.objects.get(message_id=message_id)
            message.status = status_mapping.get(status, message.status)
            message.save(update_fields=['status', 'updated_at'])
            logger.info(f"Updated status of message {message_id} to {status}")
        except Message.DoesNotExist:
            logger.warning(f"Message with ID {message_id} not found for status update")
    except Exception as e:
        logger.error(f"Error processing message status: {str(e)}")
        raise

def dashboard(request):
    """
    WhatsApp dashboard view
    """
    phone_numbers = PhoneNumber.objects.all()
    recent_messages = Message.objects.all().order_by('-timestamp')[:50]
    
    context = {
        'title': 'WhatsApp Dashboard',
        'phone_numbers': phone_numbers,
        'recent_messages': recent_messages,
    }
    return render(request, 'whatsapp/dashboard.html', context)
