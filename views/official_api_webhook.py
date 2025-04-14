import json
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from superapp.apps.whatsapp.models import PhoneNumber, Message, Contact

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request, webhook_token):
    """
    Main webhook endpoint for WhatsApp Business API
    
    Args:
        webhook_token: Required token to identify the phone number
    """
    # First, try to find the phone number by webhook_token
    try:
        phone_number = PhoneNumber.objects.get(webhook_token=webhook_token, api_type='official')
        logger.info(f"Found phone number: {phone_number.phone_number} for webhook_token: {webhook_token}")
    except PhoneNumber.DoesNotExist:
        logger.warning(f"No phone number found with webhook_token: {webhook_token}")
        return HttpResponse('Invalid webhook token', status=403)
    
    if request.method == 'GET':
        # Handle verification request from WhatsApp
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        # Verify the token matches the phone number's verify_token
        if token != phone_number.verify_token:
            logger.warning(f"Verification failed: Token mismatch for phone number: {phone_number.phone_number}")
            return HttpResponse('Verification failed: invalid token', status=403)

        if mode == 'subscribe':
            return HttpResponse(challenge)
        else:
            logger.warning(f"Invalid mode in webhook verification: {mode}")
            return HttpResponse('Verification failed: invalid mode', status=403)

    elif request.method == 'POST':
        # Handle webhook events from WhatsApp
        try:
            data = json.loads(request.body)
            logger.info(f"Received WhatsApp webhook for {phone_number.display_name}: {data}")

            # Process the webhook data for this specific phone number
            process_webhook_data(data, phone_number)

            return HttpResponse('OK')
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.exception(f"Error processing webhook: {str(e)}")
            return HttpResponse(str(e), status=500)

    return HttpResponse('Method not allowed', status=405)


def process_webhook_data(data, phone_number=None):
    """
    Process webhook data from WhatsApp Business API
    
    The webhook data structure follows the format described in:
    https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
    
    Args:
        data: The webhook data from WhatsApp
        phone_number: The PhoneNumber object associated with this webhook
    """
    # Check if this is a WhatsApp Business Account webhook
    if data.get('object') != 'whatsapp_business_account':
        logger.warning(f"Received webhook for unsupported object type: {data.get('object')}")
        return

    # Process each entry in the webhook
    for entry in data.get('entry', []):
        # Get the WhatsApp Business Account ID
        business_account_id = entry.get('id')

        # Process each change in the entry
        for change in entry.get('changes', []):
            field = change.get('field')
            value = change.get('value', {})
            
            # Process message field changes
            if field == 'messages':
                # Get metadata
                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')

                # Verify the phone_number_id matches our phone number
                if phone_number and phone_number.phone_number_id != phone_number_id:
                    logger.warning(f"Phone number ID mismatch: expected {phone_number.phone_number_id}, got {phone_number_id}")
                    continue

                # Process contacts
                contacts = value.get('contacts', [])
                for contact_data in contacts:
                    process_contact(contact_data)

                # Process messages
                messages = value.get('messages', [])
                for message_data in messages:
                    process_message(phone_number, message_data)

                # Process status updates
                statuses = value.get('statuses', [])
                for status_data in statuses:
                    process_status_update(phone_number, status_data)
            
            # Process template-related events
            elif field in ['message_template_status_update', 
                          'message_template_quality_update', 
                          'message_template_components_update']:
                
                # Log the template event
                logger.info(f"Received template event {field} for {phone_number.display_name}: {value}")
                
                # Fetch templates for this phone number
                try:
                    templates = phone_number.fetch_templates()
                    if templates:
                        logger.info(f"Successfully fetched {len(templates)} templates for {phone_number.phone_number}")
                    else:
                        logger.warning(f"No templates fetched for {phone_number.phone_number}")
                except Exception as e:
                    logger.error(f"Error fetching templates for {phone_number.phone_number}: {str(e)}")
            
            else:
                logger.info(f"Skipping unhandled field change: {field}")


def process_contact(contact_data):
    """
    Process a contact from the webhook
    """
    wa_id = contact_data.get('wa_id')
    if not wa_id:
        logger.warning("Contact data missing wa_id")
        return None

    profile = contact_data.get('profile', {})
    name = profile.get('name', wa_id)

    # Get or create the contact
    contact, created = Contact.objects.get_or_create(
        phone_number=wa_id,
        defaults={'name': name}
    )

    # Update name if it changed and we have a name
    if not created and name != wa_id and name != contact.name:
        contact.name = name
        contact.save(update_fields=['name'])

    return contact


def process_message(phone_number, message_data):
    """
    Process a message from the webhook
    """
    message_id = message_data.get('id')
    from_number = message_data.get('from')
    timestamp = message_data.get('timestamp')
    message_type = message_data.get('type')

    if not all([message_id, from_number, timestamp, message_type]):
        logger.warning(f"Message data missing required fields: {message_data}")
        return

    # Convert timestamp to datetime
    try:
        # Use timezone.now() timezone for consistency
        message_timestamp = datetime.fromtimestamp(int(timestamp))
        message_timestamp = timezone.make_aware(message_timestamp)
    except (ValueError, TypeError):
        logger.warning(f"Invalid timestamp: {timestamp}")
        message_timestamp = timezone.now()

    # Get or create the contact
    contact = Contact.objects.filter(phone_number=from_number).first()
    if not contact:
        # Try to create contact from the message data
        contact = Contact.objects.create(
            phone_number=from_number,
            name=from_number
        )

    # Create a new message record with basic info
    message = Message(
        phone_number=phone_number,
        contact=contact,
        message_id=message_id,
        from_number=from_number,
        to_number=phone_number.phone_number,
        direction='incoming',
        status='received',
        timestamp=message_timestamp,
        message_type=message_type  # Set the message type from the webhook
    )

    # Process different message types
    if message_type == 'text':
        text_data = message_data.get('text', {})
        message.content = text_data.get('body', '')

    elif message_type == 'image':
        image_data = message_data.get('image', {})
        message.media_type = 'image'
        message.content_type = 'media'
        message.media_file = None  # Will be set after downloading

        # Store media ID and other metadata
        media_id = image_data.get('id')
        message.media_id = media_id
        message.mime_type = image_data.get('mime_type', 'image/jpeg')

        if media_id:
            download_and_attach_media(message, media_id, 'image', phone_number)

        # Set caption if available
        message.content = image_data.get('caption', '')

    elif message_type == 'video':
        video_data = message_data.get('video', {})
        message.media_type = 'video'
        message.content_type = 'media'
        message.media_file = None

        # Store media ID and other metadata
        media_id = video_data.get('id')
        message.media_id = media_id
        message.media_mime_type = video_data.get('mime_type', 'video/mp4')

        if media_id:
            download_and_attach_media(message, media_id, 'video', phone_number)

        message.content = video_data.get('caption', '')

    elif message_type == 'audio':
        audio_data = message_data.get('audio', {})
        message.media_type = 'audio'
        message.content_type = 'media'
        message.media_file = None

        # Store media ID and other metadata
        media_id = audio_data.get('id')
        message.media_id = media_id
        message.mime_type = audio_data.get('mime_type', 'audio/mp3')

        if media_id:
            download_and_attach_media(message, media_id, 'audio', phone_number)

    elif message_type == 'document':
        document_data = message_data.get('document', {})
        message.media_type = 'document'
        message.content_type = 'media'
        message.media_file = None

        # Store media ID and other metadata
        media_id = document_data.get('id')
        message.media_id = media_id
        message.mime_type = document_data.get('mime_type', 'application/pdf')
        message.filename = document_data.get('filename', '')

        if media_id:
            download_and_attach_media(message, media_id, 'document', phone_number)

        message.content = document_data.get('caption', '')

    elif message_type == 'location':
        location_data = message_data.get('location', {})
        message.content_type = 'location'
        message.content = f"Location: {location_data.get('name', 'Unknown')}"

        # Store location data in metadata and specific fields
        message.metadata = {
            'location': {
                'latitude': location_data.get('latitude'),
                'longitude': location_data.get('longitude'),
                'name': location_data.get('name'),
                'address': location_data.get('address')
            }
        }

        # Store location coordinates in dedicated fields if available
        if 'latitude' in location_data and 'longitude' in location_data:
            message.latitude = location_data.get('latitude')
            message.longitude = location_data.get('longitude')

    elif message_type == 'contacts':
        contacts_data = message_data.get('contacts', [])
        message.content_type = 'contact'
        message.content = f"Shared {len(contacts_data)} contact(s)"
        message.metadata = {'contacts': contacts_data}

    elif message_type == 'interactive':
        interactive_data = message_data.get('interactive', {})
        interactive_type = interactive_data.get('type')
        message.content_type = 'interactive'

        if interactive_type == 'button_reply':
            button_reply = interactive_data.get('button_reply', {})
            message.content = button_reply.get('title', '')
            message.metadata = {
                'interactive': {
                    'type': 'button_reply',
                    'button_id': button_reply.get('id')
                }
            }

        elif interactive_type == 'list_reply':
            list_reply = interactive_data.get('list_reply', {})
            message.content = list_reply.get('title', '')
            message.metadata = {
                'interactive': {
                    'type': 'list_reply',
                    'list_id': list_reply.get('id'),
                    'description': list_reply.get('description')
                }
            }

    elif message_type == 'button':
        button_data = message_data.get('button', {})
        message.content = button_data.get('text', '')
        message.metadata = {
            'button': {
                'payload': button_data.get('payload')
            }
        }

    elif message_type == 'reaction':
        reaction_data = message_data.get('reaction', {})
        message.content = f"Reacted with {reaction_data.get('emoji', '')}"
        message.metadata = {
            'reaction': {
                'message_id': reaction_data.get('message_id'),
                'emoji': reaction_data.get('emoji')
            }
        }

    elif message_type == 'order':
        order_data = message_data.get('order', {})
        message.content = f"Order from catalog {order_data.get('catalog_id', '')}"
        message.metadata = {'order': order_data}

    elif message_type == 'sticker':
        sticker_data = message_data.get('sticker', {})
        message.media_type = 'sticker'
        message.content_type = 'media'
        message.media_file = None

        # Store media ID and other metadata
        media_id = sticker_data.get('id')
        message.media_id = media_id
        message.mime_type = sticker_data.get('mime_type', 'image/webp')

        if media_id:
            download_and_attach_media(message, media_id, 'sticker', phone_number)

    elif message_type == 'system':
        system_data = message_data.get('system', {})
        message.content = system_data.get('body', '')

        # Handle user_changed_number system message
        if system_data.get('type') == 'user_changed_number':
            message.metadata = {
                'system': {
                    'type': 'user_changed_number',
                    'new_wa_id': system_data.get('new_wa_id')
                }
            }

            # Update contact if needed
            if system_data.get('new_wa_id'):
                try:
                    # Update the contact's phone number
                    contact.phone_number = system_data.get('new_wa_id')
                    contact.save(update_fields=['phone_number'])
                except Exception as e:
                    logger.error(f"Error updating contact phone number: {str(e)}")
        else:
            message.metadata = {'system': system_data}

    elif message_type == 'unknown' or message_type == 'unsupported':
        message.content = "Unsupported message type"
        if 'errors' in message_data:
            message.metadata = {'errors': message_data.get('errors')}

    # Process context if present (for replies)
    context = message_data.get('context')
    if context:
        message.reply_to_message_id = context.get('id')

    # Process referral if present
    referral = message_data.get('referral')
    if referral:
        if message.metadata:
            metadata = message.metadata
            metadata['referral'] = referral
            message.metadata = metadata
        else:
            message.metadata = {'referral': referral}

    # Save the raw message data
    message.raw_message = message_data
    
    # Save the message
    message.save()
    logger.info(f"Saved incoming message: {message_id} from {from_number}")
    return message


def process_status_update(phone_number, status_data):
    """
    Process a status update from the webhook
    """
    message_id = status_data.get('id')
    status = status_data.get('status')
    timestamp = status_data.get('timestamp')
    recipient_id = status_data.get('recipient_id')

    if not all([message_id, status, timestamp]):
        logger.warning(f"Status data missing required fields: {status_data}")
        return

    try:
        # Find the message by ID
        message = Message.objects.get(message_id=message_id)

        # Update the status
        message.status = status

        # Convert timestamp to datetime if available
        try:
            status_timestamp = datetime.fromtimestamp(int(timestamp))
            status_timestamp = timezone.make_aware(status_timestamp)
            message.delivered_at = status_timestamp if status == 'delivered' else message.delivered_at
            message.read_at = status_timestamp if status == 'read' else message.read_at
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp in status update: {timestamp}")

        # Store conversation information if available
        conversation = status_data.get('conversation', {})
        if conversation:
            conversation_id = conversation.get('id')
            expiration = conversation.get('expiration_timestamp')
            origin_type = conversation.get('origin', {}).get('type')

            if conversation_id:
                message.conversation_id = conversation_id

            # Store conversation data in metadata
            if message.metadata:
                metadata = message.metadata
                metadata['conversation'] = conversation
                message.metadata = metadata
            else:
                message.metadata = {'conversation': conversation}

        # Store pricing information if available
        pricing = status_data.get('pricing', {})
        if pricing:
            if message.metadata:
                metadata = message.metadata
                metadata['pricing'] = pricing
                message.metadata = metadata
            else:
                message.metadata = {'pricing': pricing}

        # If there are errors, store them in metadata
        if 'errors' in status_data:
            errors = status_data.get('errors', [])
            if message.metadata:
                metadata = message.metadata
                metadata['errors'] = errors
                message.metadata = metadata
            else:
                message.metadata = {'errors': errors}

            # Store the first error code and message
            if errors and isinstance(errors, list) and len(errors) > 0:
                first_error = errors[0]
                message.error_code = first_error.get('code', 0)
                message.error_message = first_error.get('title', '')

        # Determine which fields to update
        update_fields = ['status', 'metadata']
        if message.delivered_at:
            update_fields.append('delivered_at')
        if message.read_at:
            update_fields.append('read_at')
        if 'conversation_id' in locals() and message.conversation_id:
            update_fields.append('conversation_id')
        if 'error_code' in locals() and message.error_code:
            update_fields.append('error_code')
            update_fields.append('error_message')

        # Save the updated message
        message.save(update_fields=update_fields)
        logger.info(f"Updated message status: {message_id} to {status}")

    except Message.DoesNotExist:
        logger.warning(f"Message not found for status update: {message_id}")


def download_and_attach_media(message, media_id, media_type, phone_number):
    """
    Download media from WhatsApp API and attach it to the message
    
    Following the WhatsApp Cloud API media endpoints:
    https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media
    """
    if not media_id or not phone_number.access_token:
        return

    try:
        import requests
        from django.conf import settings

        # Step 1: Retrieve the media URL
        media_info_url = f"{settings.WHATSAPP_API_URL}/{media_id}"

        headers = {
            'Authorization': f'Bearer {phone_number.access_token}'
        }

        # Optional parameter to verify the phone number ID
        params = {
            'phone_number_id': phone_number.phone_number_id
        }

        response = requests.get(media_info_url, headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to get media URL: {response.text}")
            return

        media_data = response.json()
        logger.info(f"Retrieved media info: {media_data}")

        # Extract media information
        media_url = media_data.get('url')
        mime_type = media_data.get('mime_type')
        file_size = media_data.get('file_size')
        sha256 = media_data.get('sha256')

        # Update mime type if available
        if mime_type:
            message.media_mime_type = mime_type

        # Store additional media metadata
        metadata = message.metadata if message.metadata else {}
        metadata['media_data'] = {
            'id': media_id,
            'mime_type': mime_type,
            'sha256': sha256,
            'file_size': file_size
        }
        message.metadata = metadata

        if not media_url:
            logger.error(f"No media URL in response: {media_data}")
            return

        # Step 2: Download the media using the URL
        # Note: The media URL is only valid for 5 minutes
        download_headers = {
            'Authorization': f'Bearer {phone_number.access_token}'
        }

        download_response = requests.get(
            media_url,
            headers=download_headers,
            stream=True
        )

        if download_response.status_code != 200:
            logger.error(f"Failed to download media: {download_response.text}")
            return

        # Generate a filename based on the message ID and media type
        extension = get_file_extension(media_type, mime_type)
        filename = f"{message.message_id}.{extension}"

        # Save the media file
        message.media_file.save(filename, ContentFile(download_response.content), save=False)

        logger.info(f"Successfully downloaded media: {media_id}")

    except Exception as e:
        logger.exception(f"Error downloading media: {str(e)}")


def get_file_extension(media_type, mime_type=None):
    """
    Get the file extension based on the media type and MIME type
    """
    # Use MIME type if available to determine the extension
    if mime_type:
        mime_to_ext = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/webp': 'webp',
            'video/mp4': 'mp4',
            'video/3gpp': '3gp',
            'audio/aac': 'aac',
            'audio/mp4': 'm4a',
            'audio/mpeg': 'mp3',
            'audio/amr': 'amr',
            'audio/ogg': 'ogg',
            'application/pdf': 'pdf',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/vnd.ms-powerpoint': 'ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
            'text/plain': 'txt'
        }
        return mime_to_ext.get(mime_type.lower(), 'bin')

    # Fallback to media type if MIME type is not available
    if media_type == 'image':
        return 'jpg'
    elif media_type == 'video':
        return 'mp4'
    elif media_type == 'audio':
        return 'mp3'
    elif media_type == 'document':
        return 'pdf'  # Default for documents
    elif media_type in ['sticker']:
        return 'webp'
    else:
        return 'bin'  # Default binary extension
