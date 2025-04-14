import json
import logging
import os

import requests
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from superapp.apps.whatsapp.models import PhoneNumber, Message, Contact
from superapp.apps.whatsapp.services.waha import WAHAService
from superapp.apps.whatsapp.views.official_api_webhook import webhook

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def waha_webhook(request):
    """
    Webhook endpoint for WAHA API events.
    
    Handles the "message" event with the following structure:
    {
      "id": "evt_01aaaaaaaaaaaaaaaaaaaaaaaa",
      "timestamp": 1634567890123,
      "session": "default",
      "metadata": {
        "user.id": "123",
        "user.email": "email@example.com"
      },
      "engine": "WEBJS",
      "event": "message",
      "payload": {
        "id": "false_11111111111@c.us_AAAAAAAAAAAAAAAAAAAA",
        "timestamp": 1666943582,
        "from": "11111111111@c.us",
        "fromMe": true,
        "source": "api",
        "to": "11111111111@c.us",
        "participant": "string",
        "body": "string",
        "hasMedia": true,
        "media": {
          "url": "http://localhost:3000/api/files/false_11111111111@c.us_AAAAAAAAAAAAAAAAAAAA.oga",
          "mimetype": "audio/jpeg",
          "filename": "example.pdf",
          "s3": {
            "Bucket": "my-bucket",
            "Key": "default/false_11111111111@c.us_AAAAAAAAAAAAAAAAAAAA.oga"
          },
          "error": null
        },
        "ack": -1,
        "ackName": "string",
        "author": "string",
        "location": {
          "description": "string",
          "latitude": "string",
          "longitude": "string"
        },
        "vCards": [
          "string"
        ],
        "_data": {},
        "replyTo": {
          "id": "AAAAAAAAAAAAAAAAAAAA",
          "participant": "11111111111@c.us",
          "body": "Hello!",
          "_data": {}
        }
      },
      "me": {
        "id": "11111111111@c.us",
        "pushName": "string"
      },
      "environment": {
        "version": "YYYY.MM.BUILD",
        "engine": "WEBJS",
        "tier": "PLUS",
        "browser": "/usr/path/to/bin/google-chrome"
      }
    }
    """
    try:
        # Parse the incoming JSON data
        payload = json.loads(request.body)
        
        # Extract the event type and session ID
        event_type = payload.get('event')
        session_id = payload.get('session')
        
        logger.info(f"Received WAHA webhook event: {event_type} for session: {session_id}")
        
        # Find the phone number associated with this session
        if not session_id:
            logger.warning("No session ID provided in webhook payload")
            return JsonResponse({"status": "error", "message": "No session ID provided"}, status=400)
        
        try:
            phone_number = PhoneNumber.objects.get(waha_session=session_id, api_type='waha')
        except PhoneNumber.DoesNotExist:
            logger.warning(f"No phone number found for WAHA session: {session_id}")
            return JsonResponse({"status": "error", "message": "Unknown session"}, status=404)
        
        # Only handle the "message" event type
        if event_type == 'message':
            # Process incoming message
            return _handle_incoming_message(payload, phone_number)
        else:
            # Log other events but don't process them
            logger.info(f"Unhandled WAHA event type: {event_type}")
            return JsonResponse({"status": "success", "message": "Event received but not processed"})
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.exception(f"Error processing WAHA webhook: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def _handle_incoming_message(payload, phone_number):
    """
    Handle incoming message events from WAHA API
    """
    try:
        # Extract message data from the new payload structure
        message_data = payload.get('payload', {})
        
        # Basic message info
        message_id = message_data.get('id')
        from_number = message_data.get('from')
        to_number = message_data.get('to') or payload.get('me', {}).get('id')
        from_me = message_data.get('fromMe', False)
        
        # Adjust direction based on fromMe flag
        direction = 'outgoing' if from_me else 'incoming'
        
        # If the direction is outgoing, swap from_number and to_number
        if direction == 'outgoing':
            from_number, to_number = to_number, from_number
        
        # Message content
        message_body = message_data.get('body', '')
        has_media = message_data.get('hasMedia', False)
        media_id = None
        downloaded_file = None
        filename = None
        
        # Default message type
        message_type = 'text'
        
        # Handle media messages
        if has_media and message_data.get('media'):
            media_info = message_data.get('media', {})
            media_type = media_info.get('mimetype', '').split('/')[0]
            original_url = media_info.get('url', '')
            filename = media_info.get('filename', '')

            # Download media file if URL is available
            downloaded_file = None
            if original_url and '/api/files/' in original_url:
                try:
                    # Extract the path after /api/files/
                    file_path = original_url.split('/api/files/')[-1]
                    
                    # Create WAHA service instance with phone number credentials
                    waha_service = WAHAService(
                        endpoint=phone_number.waha_endpoint,
                        username=phone_number.waha_username,
                        password=phone_number.waha_password,
                        session=phone_number.waha_session
                    )
                    
                    # Build the full URL for the file
                    full_url = f"{phone_number.waha_endpoint.rstrip('/')}/api/files/{file_path}"
                    logger.info(f"Downloading media from: {full_url}")

                    # Get the file extension from the URL or mimetype
                    if not filename:
                        if '.' in file_path:
                            filename = os.path.basename(file_path)
                        else:
                            ext = media_info.get('mimetype', '').split('/')[-1]
                            filename = f"{message_id}.{ext}"

                    # Use the WAHA service's authentication for the request
                    headers = {'Authorization': waha_service._get_auth_header()}
                    response = requests.get(full_url, headers=headers, stream=True)
                    
                    if response.status_code == 200:
                        downloaded_file = ContentFile(response.content, name=filename)
                        logger.info(f"Successfully downloaded media file: {filename}")
                    else:
                        logger.error(f"Failed to download media file: {response.status_code} - {response.text}")
                        raise Exception(f"Failed to download media file: {response.status_code}")

                except Exception as e:
                    logger.error(f"Error downloading media file: {str(e)}")
                    raise Exception(f"Error downloading media file: {str(e)}")
            
            if media_type == 'image':
                message_type = 'image'
                message_body = message_body or 'Image received'
            elif media_type == 'video':
                message_type = 'video'
                message_body = message_body or 'Video received'
            elif media_type == 'audio':
                message_type = 'audio'
                message_body = 'Audio received'
            elif media_type == 'application' or filename:
                message_type = 'document'
                message_body = filename or 'Document received'
            else:
                message_type = 'document'
                message_body = f'Media of type {media_info.get("mimetype")} received'
        
        # Check for location data
        if message_data.get('location'):
            message_type = 'location'
            location = message_data.get('location', {})
            message_body = f"Location: {location.get('description', '')} ({location.get('latitude', '')}, {location.get('longitude', '')})"
        
        # Check for vCards (contacts)
        if message_data.get('vCards') and len(message_data.get('vCards', [])) > 0:
            message_type = 'interactive'  # Using interactive as a placeholder for contact cards
            message_body = f"Contact card received: {len(message_data.get('vCards'))} contact(s)"
        
        # Check if this is a reply to another message
        reply_to = None
        if message_data.get('replyTo'):
            reply_to = {
                'id': message_data.get('replyTo', {}).get('id'),
                'body': message_data.get('replyTo', {}).get('body'),
                'participant': message_data.get('replyTo', {}).get('participant')
            }
        
        logger.info(f"Received message from {from_number}: {message_body} (type: {message_type})")
        
        # Get or create contact
        contact = None
        # Clean phone number by removing @c.us suffix if present
        clean_phone_number = from_number.split('@')[0] if '@' in from_number else from_number
        
        try:
            contact = Contact.objects.get(phone_number=clean_phone_number)
        except Contact.DoesNotExist:
            # Create a basic contact record if it doesn't exist
            if direction == 'incoming':  # Only create for incoming messages
                # Extract author name or use phone number as fallback
                contact_name = message_data.get('author') or clean_phone_number
                
                contact = Contact.objects.create(
                    phone_number=clean_phone_number,
                    name=contact_name,
                    created_at=timezone.now()
                )
                logger.info(f"Created new contact for {clean_phone_number}")
        
        # Convert WAHA timestamp to datetime if available
        timestamp = None
        if message_data.get('timestamp'):
            try:
                # WAHA timestamps are in seconds, convert to milliseconds for Django
                timestamp = timezone.datetime.fromtimestamp(
                    message_data.get('timestamp'),
                    tz=timezone.get_current_timezone()
                )
            except (ValueError, TypeError):
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()
        
        # Save the message to the database
        message = Message.objects.create(
            phone_number=phone_number,
            contact=contact,
            message_id=message_id,
            from_number=from_number,
            to_number=to_number,
            direction=direction,
            message_type=message_type,
            content=message_body,
            media_id=media_id,
            timestamp=timestamp,
            status='received' if direction == 'incoming' else 'sent',
            raw_message=json.dumps(message_data)
        )
        
        # If we have a downloaded file, save it to the media_url field
        if downloaded_file:
            message.media_file.save(filename, downloaded_file, save=True)
            logger.info(f"Saved media file to message ID: {message.id}")
        
        logger.info(f"Saved message to database with ID: {message.id}")
        
        # Return success response with the saved message details
        return JsonResponse({
            "status": "success",
            "message": "Message received and saved",
            "message_id": message_id,
            "message_type": message_type,
            "db_id": message.id
        })
        
    except Exception as e:
        logger.exception(f"Error handling incoming message: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def _handle_session_status(payload, phone_number):
    """
    Handle session status change events from WAHA API
    """
    try:
        status_data = payload.get('data', {})
        status = status_data.get('status')
        
        logger.info(f"Session status changed for {phone_number.phone_number}: {status}")
        
        # Update the phone number's configuration status based on session status
        if status == 'CONNECTED':
            if not phone_number.is_configured:
                phone_number.is_configured = True
                phone_number.save(update_fields=['is_configured'])
                logger.info(f"Marked phone number {phone_number.phone_number} as configured")
        elif status in ['DISCONNECTED', 'FAILED']:
            if phone_number.is_configured:
                phone_number.is_configured = False
                phone_number.save(update_fields=['is_configured'])
                logger.info(f"Marked phone number {phone_number.phone_number} as not configured")
        
        return JsonResponse({
            "status": "success",
            "message": "Session status updated"
        })
        
    except Exception as e:
        logger.exception(f"Error handling session status: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
