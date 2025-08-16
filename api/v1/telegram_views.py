"""
API views for Telegram webhook handling.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """Handle Telegram webhook updates."""
    try:
        # Validate webhook secret if configured
        webhook_secret = request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN')
        if hasattr(settings, 'TELEGRAM_WEBHOOK_SECRET') and settings.TELEGRAM_WEBHOOK_SECRET:
            if webhook_secret != settings.TELEGRAM_WEBHOOK_SECRET:
                logger.warning("Invalid webhook secret")
                return JsonResponse({'error': 'Invalid webhook secret'}, status=403)
        
        # Parse webhook data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Process update with bot instance
        from core.telegram_bot import bot_instance
        import asyncio
        
        async def process_update():
            try:
                from telegram import Update
                update = Update.de_json(data, bot_instance.application.bot)
                await bot_instance.application.process_update(update)
            except Exception as e:
                logger.error(f"Error processing Telegram update: {str(e)}")
        
        # Run the async function
        asyncio.run(process_update())
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def webhook_info(request):
    """Get webhook information."""
    try:
        from core.telegram_bot import bot_instance
        import asyncio
        
        async def get_webhook_info():
            try:
                webhook_info = await bot_instance.application.bot.get_webhook_info()
                return {
                    'url': webhook_info.url,
                    'has_custom_certificate': webhook_info.has_custom_certificate,
                    'pending_update_count': webhook_info.pending_update_count,
                    'last_error_date': webhook_info.last_error_date.isoformat() if webhook_info.last_error_date else None,
                    'last_error_message': webhook_info.last_error_message,
                    'max_connections': webhook_info.max_connections,
                    'allowed_updates': webhook_info.allowed_updates
                }
            except Exception as e:
                logger.error(f"Error getting webhook info: {str(e)}")
                return {'error': str(e)}
        
        info = asyncio.run(get_webhook_info())
        return JsonResponse(info)
        
    except Exception as e:
        logger.error(f"Webhook info error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def set_webhook(request):
    """Set Telegram webhook URL."""
    try:
        # Only allow admin access
        admin_token = request.META.get('HTTP_X_ADMIN_TOKEN')
        if admin_token != getattr(settings, 'ADMIN_API_TOKEN', 'admin123'):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        data = json.loads(request.body)
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            return JsonResponse({'error': 'webhook_url required'}, status=400)
        
        from core.telegram_bot import bot_instance
        import asyncio
        
        async def set_webhook_url():
            try:
                await bot_instance.application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query", "inline_query"],
                    secret_token=getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', None)
                )
                return {'status': 'success', 'webhook_url': webhook_url}
            except Exception as e:
                logger.error(f"Error setting webhook: {str(e)}")
                return {'error': str(e)}
        
        result = asyncio.run(set_webhook_url())
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Set webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_webhook(request):
    """Delete Telegram webhook."""
    try:
        # Only allow admin access
        admin_token = request.META.get('HTTP_X_ADMIN_TOKEN')
        if admin_token != getattr(settings, 'ADMIN_API_TOKEN', 'admin123'):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        from core.telegram_bot import bot_instance
        import asyncio
        
        async def delete_webhook_url():
            try:
                await bot_instance.application.bot.delete_webhook()
                return {'status': 'success', 'message': 'Webhook deleted'}
            except Exception as e:
                logger.error(f"Error deleting webhook: {str(e)}")
                return {'error': str(e)}
        
        result = asyncio.run(delete_webhook_url())
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Delete webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
