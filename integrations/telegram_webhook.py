"""
Telegram Webhook Setup for Production Deployment
"""

import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from telegram import Update
from telegram.ext import Application
import json
import asyncio
from notifications.telegram import telegram_service

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """
    Handle incoming Telegram webhook updates
    """
    try:
        # Parse the JSON data from Telegram
        json_data = json.loads(request.body.decode('utf-8'))
        
        # Create Update object
        update = Update.de_json(json_data, None)
        
        if update:
            # For now, just log the update - bot functionality can be added later
            logger.info(f"Received Telegram update: {update.update_id}")
            return HttpResponse("OK")
        else:
            logger.warning("Invalid update received from Telegram")
            return HttpResponse("Invalid update", status=400)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON received from Telegram webhook")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")
        return HttpResponse("Internal error", status=500)


async def setup_webhook():
    """
    Set up Telegram webhook URL
    Call this during application startup
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token not configured")
            return False
            
        # Get the bot instance
        bot = telegram_service.bot
        
        # Construct webhook URL
        webhook_url = f"https://{settings.ALLOWED_HOSTS[0]}/api/v1/telegram/webhook/"
        
        # Set webhook
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        logger.info(f"Telegram webhook set to: {webhook_url}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup Telegram webhook: {e}")
        return False


def remove_telegram_webhook():
    """
    Remove Telegram webhook (for development/testing)
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            return False
            
        application = get_application()
        bot = application.bot
        
        # Remove webhook
        asyncio.run(bot.delete_webhook())
        
        logger.info("Telegram webhook removed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to remove Telegram webhook: {e}")
        return False


def get_webhook_info():
    """
    Get current webhook information
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            return {"error": "Bot token not configured"}
            
        application = get_application()
        bot = application.bot
        
        # Get webhook info
        webhook_info = asyncio.run(bot.get_webhook_info())
        
        return {
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates
        }
        
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        return {"error": str(e)}
