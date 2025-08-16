"""
Telegram Bot Handlers for Payment Verification
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
import logging
from core.payment_verification import payment_verification_manager
from core.models import Payment

logger = logging.getLogger(__name__)


def handle_payment_approval_callback(update: Update, context: CallbackContext):
    """Handle approve/deny payment callback from Telegram buttons"""
    try:
        query = update.callback_query
        query.answer()
        
        # Parse callback data
        callback_data = query.data
        if callback_data.startswith('approve_payment_'):
            payment_id = int(callback_data.replace('approve_payment_', ''))
            action = 'approve'
        elif callback_data.startswith('deny_payment_'):
            payment_id = int(callback_data.replace('deny_payment_', ''))
            action = 'deny'
        else:
            query.edit_message_text("❌ Invalid callback data")
            return
        
        # Get admin user ID
        admin_user_id = str(query.from_user.id)
        admin_name = query.from_user.first_name or query.from_user.username
        
        if action == 'approve':
            # Show approval confirmation with comment option
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm Approval", 
                                       callback_data=f"confirm_approve_{payment_id}"),
                    InlineKeyboardButton("💬 Add Comment", 
                                       callback_data=f"comment_approve_{payment_id}")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"🔍 **Confirm Payment Approval**\n\n"
                f"Payment ID: {payment_id}\n"
                f"Admin: {admin_name}\n\n"
                f"Are you sure you want to approve this payment?",
                reply_markup=reply_markup
            )
            
        else:  # deny
            # Show denial confirmation with reason option
            keyboard = [
                [
                    InlineKeyboardButton("❌ Confirm Denial", 
                                       callback_data=f"confirm_deny_{payment_id}"),
                    InlineKeyboardButton("📝 Add Reason", 
                                       callback_data=f"reason_deny_{payment_id}")
                ],
                [InlineKeyboardButton("✅ Cancel", callback_data="cancel_action")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"🔍 **Confirm Payment Denial**\n\n"
                f"Payment ID: {payment_id}\n"
                f"Admin: {admin_name}\n\n"
                f"Are you sure you want to deny this payment?",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Payment callback handler error: {e}")
        query.edit_message_text("❌ Error processing request")


def handle_payment_confirmation_callback(update: Update, context: CallbackContext):
    """Handle final confirmation of approve/deny actions"""
    try:
        query = update.callback_query
        query.answer()
        
        callback_data = query.data
        admin_user_id = str(query.from_user.id)
        admin_name = query.from_user.first_name or query.from_user.username
        
        if callback_data.startswith('confirm_approve_'):
            payment_id = int(callback_data.replace('confirm_approve_', ''))
            
            # Approve payment
            result = payment_verification_manager.approve_payment(
                payment_id=payment_id,
                admin_user_id=admin_user_id,
                admin_comments=f"Approved by {admin_name} via Telegram"
            )
            
            if result['status'] == 'success':
                query.edit_message_text(
                    f"✅ **Payment Approved**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Approved by: {admin_name}\n"
                    f"Time: {context.bot.get_chat(query.message.chat_id).title}\n\n"
                    f"Student has been notified."
                )
            else:
                query.edit_message_text(
                    f"❌ **Approval Failed**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Error: {result['message']}"
                )
                
        elif callback_data.startswith('confirm_deny_'):
            payment_id = int(callback_data.replace('confirm_deny_', ''))
            
            # Deny payment
            result = payment_verification_manager.deny_payment(
                payment_id=payment_id,
                admin_user_id=admin_user_id,
                reason=f"Denied by {admin_name} via Telegram"
            )
            
            if result['status'] == 'success':
                query.edit_message_text(
                    f"❌ **Payment Denied**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Denied by: {admin_name}\n"
                    f"Time: {context.bot.get_chat(query.message.chat_id).title}\n\n"
                    f"Student has been notified."
                )
            else:
                query.edit_message_text(
                    f"❌ **Denial Failed**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Error: {result['message']}"
                )
                
        elif callback_data == 'cancel_action':
            query.edit_message_text("🚫 Action cancelled")
            
    except Exception as e:
        logger.error(f"Payment confirmation handler error: {e}")
        query.edit_message_text("❌ Error processing confirmation")


def handle_comment_reason_callback(update: Update, context: CallbackContext):
    """Handle adding comments/reasons to payment decisions"""
    try:
        query = update.callback_query
        query.answer()
        
        callback_data = query.data
        
        if callback_data.startswith('comment_approve_'):
            payment_id = callback_data.replace('comment_approve_', '')
            context.user_data['pending_approval'] = payment_id
            query.edit_message_text(
                f"💬 **Add Approval Comment**\n\n"
                f"Payment ID: {payment_id}\n\n"
                f"Please send your comment for this approval:"
            )
            
        elif callback_data.startswith('reason_deny_'):
            payment_id = callback_data.replace('reason_deny_', '')
            context.user_data['pending_denial'] = payment_id
            query.edit_message_text(
                f"📝 **Add Denial Reason**\n\n"
                f"Payment ID: {payment_id}\n\n"
                f"Please send the reason for denying this payment:"
            )
            
    except Exception as e:
        logger.error(f"Comment/reason handler error: {e}")
        query.edit_message_text("❌ Error processing request")


def handle_payment_comment_message(update: Update, context: CallbackContext):
    """Handle text messages for payment comments/reasons"""
    try:
        user_id = str(update.effective_user.id)
        message_text = update.message.text
        admin_name = update.effective_user.first_name or update.effective_user.username
        
        # Check if user has pending approval
        if 'pending_approval' in context.user_data:
            payment_id = int(context.user_data['pending_approval'])
            del context.user_data['pending_approval']
            
            # Approve with comment
            result = payment_verification_manager.approve_payment(
                payment_id=payment_id,
                admin_user_id=user_id,
                admin_comments=message_text
            )
            
            if result['status'] == 'success':
                update.message.reply_text(
                    f"✅ **Payment Approved with Comment**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Approved by: {admin_name}\n"
                    f"Comment: {message_text}\n\n"
                    f"Student has been notified."
                )
            else:
                update.message.reply_text(
                    f"❌ **Approval Failed**\n\n"
                    f"Error: {result['message']}"
                )
                
        # Check if user has pending denial
        elif 'pending_denial' in context.user_data:
            payment_id = int(context.user_data['pending_denial'])
            del context.user_data['pending_denial']
            
            # Deny with reason
            result = payment_verification_manager.deny_payment(
                payment_id=payment_id,
                admin_user_id=user_id,
                reason=message_text
            )
            
            if result['status'] == 'success':
                update.message.reply_text(
                    f"❌ **Payment Denied with Reason**\n\n"
                    f"Payment ID: {payment_id}\n"
                    f"Denied by: {admin_name}\n"
                    f"Reason: {message_text}\n\n"
                    f"Student has been notified."
                )
            else:
                update.message.reply_text(
                    f"❌ **Denial Failed**\n\n"
                    f"Error: {result['message']}"
                )
                
    except Exception as e:
        logger.error(f"Payment comment message handler error: {e}")
        update.message.reply_text("❌ Error processing your message")


def handle_pending_payments_command(update: Update, context: CallbackContext):
    """Handle /pending_payments command"""
    try:
        user_id = str(update.effective_user.id)
        
        # Check if user is admin
        admin_ids = context.bot_data.get('admin_ids', [])
        if user_id not in admin_ids:
            update.message.reply_text("❌ Admin access required")
            return
        
        # Get pending verifications
        pending = payment_verification_manager.get_pending_verifications()
        
        if not pending:
            update.message.reply_text("✅ No pending payment verifications")
            return
        
        message = f"📋 **Pending Payment Verifications** ({len(pending)})\n\n"
        
        for payment in pending[:10]:  # Show max 10
            days_pending = payment['days_pending']
            urgency = "🔴" if days_pending > 2 else "🟡" if days_pending > 1 else "🟢"
            
            message += f"{urgency} **{payment['student_name']}**\n"
            message += f"   💰 ₹{payment['amount']} | ID: {payment['payment_id']}\n"
            message += f"   📅 {days_pending} days pending\n"
            message += f"   📄 [Receipt]({payment['receipt_url']})\n\n"
        
        if len(pending) > 10:
            message += f"... and {len(pending) - 10} more\n\n"
        
        message += f"📊 [Open Verification Sheet](https://docs.google.com/spreadsheets/d/{context.bot_data.get('verification_sheet_id', '')})"
        
        update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Pending payments command error: {e}")
        update.message.reply_text("❌ Error getting pending payments")


# Register handlers
def register_payment_handlers(application):
    """Register payment verification handlers with the bot"""
    
    # Callback handlers
    application.add_handler(
        CallbackQueryHandler(
            handle_payment_approval_callback,
            pattern=r'^(approve_payment_|deny_payment_)\d+$'
        )
    )
    
    application.add_handler(
        CallbackQueryHandler(
            handle_payment_confirmation_callback,
            pattern=r'^(confirm_approve_|confirm_deny_)\d+$|^cancel_action$'
        )
    )
    
    application.add_handler(
        CallbackQueryHandler(
            handle_comment_reason_callback,
            pattern=r'^(comment_approve_|reason_deny_)\d+$'
        )
    )
    
    # Command handlers
    from telegram.ext import CommandHandler
    application.add_handler(
        CommandHandler('pending_payments', handle_pending_payments_command)
    )
    
    # Message handler for comments/reasons
    from telegram.ext import MessageHandler, filters
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_payment_comment_message
        )
    )
