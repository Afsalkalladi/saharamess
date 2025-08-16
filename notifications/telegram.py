import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from telegram import Bot
from telegram.error import TelegramError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """Service for sending Telegram notifications."""
    
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.admin_ids = settings.ADMIN_TG_IDS
    
    async def send_message(self, chat_id: int, message: str, parse_mode='Markdown') -> bool:
        """Send a message to a specific chat."""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info(f"Message sent successfully to {chat_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send message to {chat_id}: {str(e)}")
            return False
    
    async def send_photo(self, chat_id: int, photo, caption: str = None) -> bool:
        """Send a photo to a specific chat."""
        try:
            await self.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode='Markdown'
            )
            logger.info(f"Photo sent successfully to {chat_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send photo to {chat_id}: {str(e)}")
            return False
    
    async def broadcast_to_admins(self, message: str) -> int:
        """Broadcast message to all admins."""
        success_count = 0
        
        for admin_id in self.admin_ids:
            if await self.send_message(admin_id, message):
                success_count += 1
        
        logger.info(f"Broadcast sent to {success_count}/{len(self.admin_ids)} admins")
        return success_count
    
    async def broadcast_to_students(self, student_ids: List[int], message: str) -> int:
        """Broadcast message to multiple students."""
        success_count = 0
        
        for student_id in student_ids:
            if await self.send_message(student_id, message):
                success_count += 1
        
        logger.info(f"Broadcast sent to {success_count}/{len(student_ids)} students")
        return success_count
    
    # Specific notification methods
    async def notify_registration_pending(self, student_data: Dict[str, Any]) -> bool:
        """Notify admins about pending registration."""
        message = f"""
📝 **New Registration Pending**

👤 **Name**: {student_data['name']}
🎓 **Roll**: {student_data['roll_no']}
🏠 **Room**: {student_data['room_no']}
📱 **Phone**: {student_data['phone']}
🆔 **Telegram ID**: {student_data['tg_user_id']}

⏰ **Applied**: {student_data.get('created_at', 'Just now')}

Use the admin panel to approve/deny this registration.
        """
        
        return await self.broadcast_to_admins(message)
    
    async def notify_registration_approved(self, student_data: Dict[str, Any]) -> bool:
        """Notify student about registration approval."""
        message = f"""
✅ **Registration Approved!**

Congratulations {student_data['name']}! 

Your mess registration has been approved. You can now:
• Upload payment screenshots
• Apply for mess cuts
• Access meals with your QR code

Your permanent QR code will be sent shortly.

Use /start to access all features.
        """
        
        return await self.send_message(student_data['tg_user_id'], message)
    
    async def notify_registration_denied(self, student_data: Dict[str, Any]) -> bool:
        """Notify student about registration denial."""
        message = f"""
❌ **Registration Denied**

Sorry {student_data['name']}, your registration could not be approved at this time.

If you believe this is an error, please contact the mess administration or try registering again with correct information.

Use /start to register again.
        """
        
        return await self.send_message(student_data['tg_user_id'], message)
    
    async def notify_payment_uploaded(self, payment_data: Dict[str, Any]) -> bool:
        """Notify admins about payment upload."""
        message = f"""
💳 **Payment Upload - Review Required**

👤 **Student**: {payment_data['student_name']} ({payment_data['student_roll']})
📅 **Period**: {payment_data['cycle_start']} to {payment_data['cycle_end']}
💰 **Amount**: ₹{payment_data['amount']}
📸 **Screenshot**: {payment_data.get('screenshot_url', 'Available')}

⏰ **Uploaded**: {payment_data.get('created_at', 'Just now')}

Use the admin panel to verify/deny this payment.
        """
        
        return await self.broadcast_to_admins(message)
    
    async def notify_payment_verified(self, payment_data: Dict[str, Any]) -> bool:
        """Notify student about payment verification."""
        message = f"""
✅ **Payment Verified!**

Your payment has been verified and approved:

📅 **Period**: {payment_data['cycle_start']} to {payment_data['cycle_end']}
💰 **Amount**: ₹{payment_data['amount']}
✅ **Status**: Verified

You can now access meals during this period. Show your QR code to the staff during meal times.
        """
        
        return await self.send_message(payment_data['student_tg_user_id'], message)
    
    async def notify_payment_denied(self, payment_data: Dict[str, Any]) -> bool:
        """Notify student about payment denial."""
        message = f"""
⚠️ **Payment Verification Failed**

Your payment screenshot could not be verified:

📅 **Period**: {payment_data['cycle_start']} to {payment_data['cycle_end']}
💰 **Amount**: ₹{payment_data['amount']}

**Possible reasons:**
• Screenshot is unclear or incomplete
• Transaction details don't match
• Invalid payment method

Please upload a clearer screenshot or contact the admin.
        """
        
        return await self.send_message(payment_data['student_tg_user_id'], message)
    
    async def notify_mess_cut_applied(self, mess_cut_data: Dict[str, Any]) -> bool:
        """Notify student about mess cut confirmation."""
        duration = (datetime.fromisoformat(mess_cut_data['to_date']) - 
                   datetime.fromisoformat(mess_cut_data['from_date'])).days + 1
        
        message = f"""
✂️ **Mess Cut Confirmed**

Your mess cut has been applied:

📅 **From**: {mess_cut_data['from_date']}
📅 **To**: {mess_cut_data['to_date']}
⏱️ **Duration**: {duration} days

You won't be charged for these days. The mess cut will be automatically applied.
        """
        
        return await self.send_message(mess_cut_data['student_tg_user_id'], message)
    
    async def notify_mess_closure(self, closure_data: Dict[str, Any], student_ids: List[int]) -> int:
        """Notify all students about mess closure."""
        duration = (datetime.fromisoformat(closure_data['to_date']) - 
                   datetime.fromisoformat(closure_data['from_date'])).days + 1
        
        reason_text = f"\n\n**Reason**: {closure_data['reason']}" if closure_data.get('reason') else ""
        
        message = f"""
📢 **Mess Closure Notice**

The mess will be closed:

📅 **From**: {closure_data['from_date']}
📅 **To**: {closure_data['to_date']}
⏱️ **Duration**: {duration} days{reason_text}

You won't be charged for these days. No action is required from your side.
        """
        
        return await self.broadcast_to_students(student_ids, message)
    
    async def notify_qr_scanned(self, scan_data: Dict[str, Any]) -> bool:
        """Notify student about successful QR scan."""
        meal_emoji = {
            'BREAKFAST': '🍳',
            'LUNCH': '🍽️',
            'DINNER': '🍽️'
        }
        
        current_time = timezone.now().strftime('%H:%M')
        current_date = timezone.now().strftime('%Y-%m-%d')
        
        message = f"""
🍽️ **Meal Access Granted**

{meal_emoji.get(scan_data['meal'], '🍽️')} **{scan_data['meal'].title()}** access confirmed

⏰ **Time**: {current_time}
📅 **Date**: {current_date}

Enjoy your meal, {scan_data['student_name']}!
        """
        
        return await self.send_message(scan_data['student_tg_user_id'], message)
    
    async def notify_qr_scan_blocked(self, scan_data: Dict[str, Any]) -> bool:
        """Notify student about blocked QR scan."""
        message = f"""
🚫 **Meal Access Denied**

Your QR scan was blocked:

**Reason**: {scan_data.get('reason', 'Access denied')}
⏰ **Time**: {timezone.now().strftime('%H:%M')}

Please check your payment status and contact admin if needed.
        """
        
        return await self.send_message(scan_data['student_tg_user_id'], message)
    
    async def send_daily_report(self, report_data: Dict[str, Any]) -> int:
        """Send daily summary report to admins."""
        message = f"""
📊 **Daily Mess Report - {report_data['date']}**

📝 **Registrations**: {report_data.get('new_registrations', 0)}
💳 **Payments Uploaded**: {report_data.get('payments_uploaded', 0)}
✅ **Payments Verified**: {report_data.get('payments_verified', 0)}
✂️ **Mess Cuts Applied**: {report_data.get('mess_cuts', 0)}

🍽️ **Meal Statistics**:
🍳 Breakfast: {report_data.get('breakfast_scans', 0)}
🍽️ Lunch: {report_data.get('lunch_scans', 0)}
🍽️ Dinner: {report_data.get('dinner_scans', 0)}

📈 **Total Successful Scans**: {report_data.get('total_scans', 0)}
📊 **Success Rate**: {report_data.get('success_rate', 0):.1f}%

💰 **Pending Reviews**: {report_data.get('pending_payments', 0)} payments
👥 **Pending Registrations**: {report_data.get('pending_registrations', 0)}
        """
        
        return await self.broadcast_to_admins(message)
    
    async def notify_payment_expiring(self, student_data: Dict[str, Any], days_left: int) -> bool:
        """Notify student about expiring payment."""
        message = f"""
⏰ **Payment Expiring Soon**

Hi {student_data['name']},

Your mess payment is expiring in {days_left} days:

📅 **Expires**: {student_data['cycle_end']}
💰 **Amount**: ₹{student_data['amount']}

Please upload your next payment to avoid service interruption.

Use /start → Upload Payment to submit your new payment.
        """
        
        return await self.send_message(student_data['tg_user_id'], message)
    
    async def notify_payment_expired(self, student_data: Dict[str, Any]) -> bool:
        """Notify student about expired payment."""
        message = f"""
❌ **Payment Expired**

Hi {student_data['name']},

Your mess payment has expired:

📅 **Expired**: {student_data['cycle_end']}
💰 **Last Amount**: ₹{student_data['amount']}

Please upload your new payment immediately to continue accessing meals.

Use /start → Upload Payment to submit your payment.
        """
        
        return await self.send_message(student_data['tg_user_id'], message)
    
    async def send_qr_code(self, student_data: Dict[str, Any], qr_image) -> bool:
        """Send QR code to student."""
        caption = f"""
🔑 **Your Mess QR Code**

👤 **Name**: {student_data['name']}
🎓 **Roll**: {student_data['roll_no']}
🏠 **Room**: {student_data['room_no']}

📱 This QR code is permanent unless admin regenerates all codes.
🚫 Please don't share with others.
⏰ Show this during meal times for access.

**Meal Timings:**
🍳 Breakfast: 7:00 AM - 9:30 AM
🍽️ Lunch: 12:00 PM - 2:30 PM
🍽️ Dinner: 7:00 PM - 9:30 PM
        """
        
        return await self.send_photo(student_data['tg_user_id'], qr_image, caption)


# Synchronous wrapper functions for use in Django views
def sync_send_message(chat_id: int, message: str) -> bool:
    """Synchronous wrapper for sending messages."""
    service = TelegramNotificationService()
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(service.send_message(chat_id, message))


def sync_notify_registration_pending(student_data: Dict[str, Any]) -> bool:
    """Synchronous wrapper for registration notification."""
    service = TelegramNotificationService()
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(service.notify_registration_pending(student_data))


def sync_notify_payment_uploaded(payment_data: Dict[str, Any]) -> bool:
    """Synchronous wrapper for payment upload notification."""
    service = TelegramNotificationService()
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(service.notify_payment_uploaded(payment_data))


def sync_send_qr_code(student_data: Dict[str, Any], qr_image) -> bool:
    """Synchronous wrapper for sending QR codes."""
    service = TelegramNotificationService()
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(service.send_qr_code(student_data, qr_image))


# Global instance
telegram_service = TelegramNotificationService()