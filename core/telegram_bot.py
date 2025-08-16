import os
import logging
from datetime import datetime, timedelta
from io import BytesIO
import requests
import cloudinary
import cloudinary.uploader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ContextTypes, filters, ConversationHandler
)
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from core.models import Student, Payment, MessCut, MessClosure
from core.services import QRService, MessService, NotificationService

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(REGISTER_NAME, REGISTER_ROLL, REGISTER_ROOM, REGISTER_PHONE,
 PAYMENT_CYCLE_START, PAYMENT_CYCLE_END, PAYMENT_AMOUNT, PAYMENT_SCREENSHOT,
 MESS_CUT_FROM, MESS_CUT_TO, MESS_CUT_CONFIRM) = range(11)


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup command and message handlers."""
        
        # Registration conversation handler
        register_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_registration, pattern='^register$')],
            states={
                REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_name)],
                REGISTER_ROLL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_roll)],
                REGISTER_ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_room)],
                REGISTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_phone)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        
        # Payment upload conversation handler
        payment_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_payment_upload, pattern='^upload_payment$')],
            states={
                PAYMENT_CYCLE_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment_cycle_start)],
                PAYMENT_CYCLE_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment_cycle_end)],
                PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment_amount)],
                PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO, self.payment_screenshot)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        
        # Mess cut conversation handler
        mess_cut_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_mess_cut, pattern='^mess_cut$')],
            states={
                MESS_CUT_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.mess_cut_from)],
                MESS_CUT_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.mess_cut_to)],
                MESS_CUT_CONFIRM: [CallbackQueryHandler(self.mess_cut_confirm, pattern='^confirm_cut|cancel_cut$')],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Conversation handlers
        self.application.add_handler(register_conv)
        self.application.add_handler(payment_conv)
        self.application.add_handler(mess_cut_conv)
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.show_qr, pattern='^show_qr$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_panel, pattern='^admin_panel$'))
        
        # Admin handlers
        self.application.add_handler(CallbackQueryHandler(self.admin_pending_registrations, pattern='^admin_pending_reg$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_payments, pattern='^admin_payments$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_approve_student, pattern='^approve_'))
        self.application.add_handler(CallbackQueryHandler(self.admin_deny_student, pattern='^deny_'))
        self.application.add_handler(CallbackQueryHandler(self.admin_verify_payment, pattern='^verify_payment_'))
        self.application.add_handler(CallbackQueryHandler(self.admin_deny_payment, pattern='^deny_payment_'))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        
        welcome_text = f"""
Hi {first_name}! 👋

Welcome to the Mess Management System! This bot helps you with:
• Registration and approval
• Payment uploads and verification  
• Mess cut applications
• Your permanent QR code for meal access

⏰ **Important**: Mess cuts for tomorrow close at 11:00 PM today.

Use the buttons below to get started:
        """
        
        # Create keyboard based on user status
        keyboard = []
        
        try:
            student = Student.objects.get(tg_user_id=user_id)
            if student.status == Student.Status.APPROVED:
                keyboard = [
                    [InlineKeyboardButton("📱 My QR Code", callback_data="show_qr")],
                    [InlineKeyboardButton("💳 Upload Payment", callback_data="upload_payment")],
                    [InlineKeyboardButton("✂️ Take Mess Cut", callback_data="mess_cut")],
                    [InlineKeyboardButton("❓ Help", callback_data="help")]
                ]
            elif student.status == Student.Status.PENDING:
                keyboard = [
                    [InlineKeyboardButton("⏳ Registration Pending", callback_data="pending")],
                    [InlineKeyboardButton("❓ Help", callback_data="help")]
                ]
            else:  # DENIED
                keyboard = [
                    [InlineKeyboardButton("❌ Registration Denied", callback_data="denied")],
                    [InlineKeyboardButton("🔄 Register Again", callback_data="register")],
                    [InlineKeyboardButton("❓ Help", callback_data="help")]
                ]
        except Student.DoesNotExist:
            keyboard = [
                [InlineKeyboardButton("📝 Register", callback_data="register")],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ]
        
        # Add admin panel for authorized users
        if user_id in settings.ADMIN_TG_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
🆘 **Help & FAQs**

**Registration:**
• Use /start and click "Register" to submit your details
• Wait for admin approval (you'll get a notification)

**Payments:**
• Upload payment screenshots for verification
• Admins will verify and notify you
• Payment must be valid for current cycle

**Mess Cuts:**
• Apply for mess cuts until 11:00 PM for next day onwards
• Cannot apply for today or past dates
• Mess closure days are automatically excluded

**QR Code:**
• Your QR is permanent unless admin regenerates all codes
• Show QR to staff during meal times
• Don't share your QR with others

**Meal Times:**
🍳 Breakfast: 7:00 AM - 9:30 AM
🍽️ Lunch: 12:00 PM - 2:30 PM  
🍽️ Dinner: 7:00 PM - 9:30 PM

**Support:** Contact mess admin if you face any issues.
        """
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(help_text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup)
    
    # Registration Flow
    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start registration process."""
        user_id = update.effective_user.id
        
        # Check if already registered
        if Student.objects.filter(tg_user_id=user_id).exists():
            await update.callback_query.answer("You are already registered!")
            return ConversationHandler.END
        
        await update.callback_query.edit_message_text(
            "📝 **Registration**\n\nPlease enter your full name:"
        )
        return REGISTER_NAME
    
    async def register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle name input."""
        name = update.message.text.strip()
        if len(name) < 2 or len(name) > 100:
            await update.message.reply_text("Please enter a valid name (2-100 characters):")
            return REGISTER_NAME
        
        context.user_data['name'] = name
        await update.message.reply_text("👨‍🎓 Please enter your roll number:")
        return REGISTER_ROLL
    
    async def register_roll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle roll number input."""
        roll_no = update.message.text.strip().upper()
        
        # Validate format
        import re
        if not re.match(r'^[A-Z0-9]+, roll_no):
            await update.message.reply_text("Roll number must contain only letters and numbers. Please try again:")
            return REGISTER_ROLL
        
        # Check if roll number already exists
        if Student.objects.filter(roll_no=roll_no).exists():
            await update.message.reply_text("This roll number is already registered. Please check and try again:")
            return REGISTER_ROLL
        
        context.user_data['roll_no'] = roll_no
        await update.message.reply_text("🏠 Please enter your room number:")
        return REGISTER_ROOM
    
    async def register_room(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle room number input."""
        room_no = update.message.text.strip()
        if len(room_no) < 1 or len(room_no) > 20:
            await update.message.reply_text("Please enter a valid room number:")
            return REGISTER_ROOM
        
        context.user_data['room_no'] = room_no
        await update.message.reply_text("📱 Please enter your phone number (with country code if international):")
        return REGISTER_PHONE
    
    async def register_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number input and complete registration."""
        phone = update.message.text.strip()
        
        # Validate phone format
        import re
        if not re.match(r'^\+?[1-9]\d{1,14}, phone):
            await update.message.reply_text("Please enter a valid phone number:")
            return REGISTER_PHONE
        
        context.user_data['phone'] = phone
        
        try:
            # Create student record
            with transaction.atomic():
                student = Student.objects.create(
                    tg_user_id=update.effective_user.id,
                    name=context.user_data['name'],
                    roll_no=context.user_data['roll_no'],
                    room_no=context.user_data['room_no'],
                    phone=context.user_data['phone']
                )
                
                # Notify admins
                await self.notify_admins_new_registration(student)
                
                await update.message.reply_text(
                    "✅ **Registration Submitted!**\n\n"
                    "Your registration has been submitted for admin approval. "
                    "You'll receive a notification once it's processed.\n\n"
                    "Use /start to return to the main menu."
                )
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            await update.message.reply_text(
                "❌ Registration failed. Please try again later or contact support."
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
    
    # Payment Upload Flow
    async def start_payment_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start payment upload process."""
        user_id = update.effective_user.id
        
        try:
            student = Student.objects.get(tg_user_id=user_id, status=Student.Status.APPROVED)
            context.user_data['student_id'] = str(student.id)
            
            await update.callback_query.edit_message_text(
                "💳 **Payment Upload**\n\n"
                "Please enter the cycle start date (YYYY-MM-DD format):\n"
                "Example: 2024-01-01"
            )
            return PAYMENT_CYCLE_START
            
        except Student.DoesNotExist:
            await update.callback_query.answer("You need to be registered and approved first!")
            return ConversationHandler.END
    
    async def payment_cycle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cycle start date."""
        try:
            date_str = update.message.text.strip()
            cycle_start = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if cycle_start < timezone.now().date():
                await update.message.reply_text("Start date cannot be in the past. Please enter a valid date:")
                return PAYMENT_CYCLE_START
            
            context.user_data['cycle_start'] = cycle_start
            await update.message.reply_text(
                "📅 Please enter the cycle end date (YYYY-MM-DD format):\n"
                "Example: 2024-01-31"
            )
            return PAYMENT_CYCLE_END
            
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
            return PAYMENT_CYCLE_START
    
    async def payment_cycle_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cycle end date."""
        try:
            date_str = update.message.text.strip()
            cycle_end = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if cycle_end <= context.user_data['cycle_start']:
                await update.message.reply_text("End date must be after start date. Please enter a valid date:")
                return PAYMENT_CYCLE_END
            
            context.user_data['cycle_end'] = cycle_end
            await update.message.reply_text("💰 Please enter the payment amount (numbers only):")
            return PAYMENT_AMOUNT
            
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
            return PAYMENT_CYCLE_END
    
    async def payment_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment amount."""
        try:
            amount = float(update.message.text.strip())
            if amount <= 0:
                await update.message.reply_text("Amount must be positive. Please enter a valid amount:")
                return PAYMENT_AMOUNT
            
            context.user_data['amount'] = amount
            await update.message.reply_text(
                "📸 Please upload a screenshot of your payment receipt:\n\n"
                "Make sure the image is clear and shows the transaction details."
            )
            return PAYMENT_SCREENSHOT
            
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter numbers only:")
            return PAYMENT_AMOUNT
    
    async def payment_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment screenshot upload."""
        try:
            # Get the largest photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Download image
            image_data = BytesIO()
            await file.download_to_memory(image_data)
            image_data.seek(0)
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                image_data,
                folder="mess_payments",
                public_id=f"payment_{context.user_data['student_id']}_{int(timezone.now().timestamp())}"
            )
            
            # Create payment record
            payment = Payment.objects.create(
                student_id=context.user_data['student_id'],
                cycle_start=context.user_data['cycle_start'],
                cycle_end=context.user_data['cycle_end'],
                amount=context.user_data['amount'],
                screenshot_url=upload_result['secure_url'],
                status=Payment.Status.UPLOADED
            )
            
            # Notify admins
            await self.notify_admins_payment_upload(payment)
            
            await update.message.reply_text(
                "✅ **Payment Uploaded!**\n\n"
                "Your payment screenshot has been uploaded and is pending admin verification. "
                "You'll receive a notification once it's processed.\n\n"
                "Use /start to return to the main menu."
            )
            
        except Exception as e:
            logger.error(f"Payment upload error: {str(e)}")
            await update.message.reply_text(
                "❌ Upload failed. Please try again later or contact support."
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
    
    # Mess Cut Flow
    async def start_mess_cut(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start mess cut process."""
        user_id = update.effective_user.id
        
        try:
            student = Student.objects.get(tg_user_id=user_id, status=Student.Status.APPROVED)
            context.user_data['student_id'] = str(student.id)
            
            # Check cutoff time
            now = timezone.now()
            cutoff_time = now.replace(hour=23, minute=0, second=0, microsecond=0)
            
            if now.time() >= cutoff_time.time():
                min_date = (now + timedelta(days=2)).date()
                cutoff_msg = f"\n\n⏰ **Note**: It's past 11:00 PM, so you can only apply for {min_date} onwards."
            else:
                min_date = (now + timedelta(days=1)).date()
                cutoff_msg = f"\n\n⏰ **Note**: Cutoff is at 11:00 PM. You can apply for {min_date} onwards."
            
            await update.callback_query.edit_message_text(
                f"✂️ **Mess Cut Application**\n\n"
                f"Please enter the FROM date (YYYY-MM-DD format):\n"
                f"Earliest allowed: {min_date}{cutoff_msg}"
            )
            
            context.user_data['min_date'] = min_date
            return MESS_CUT_FROM
            
        except Student.DoesNotExist:
            await update.callback_query.answer("You need to be registered and approved first!")
            return ConversationHandler.END
    
    async def mess_cut_from(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mess cut from date."""
        try:
            date_str = update.message.text.strip()
            from_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            min_date = context.user_data['min_date']
            
            if from_date < min_date:
                await update.message.reply_text(
                    f"From date cannot be earlier than {min_date}. Please enter a valid date:"
                )
                return MESS_CUT_FROM
            
            context.user_data['from_date'] = from_date
            await update.message.reply_text(
                "📅 Please enter the TO date (YYYY-MM-DD format):\n"
                "Must be on or after the FROM date."
            )
            return MESS_CUT_TO
            
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
            return MESS_CUT_FROM
    
    async def mess_cut_to(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mess cut to date."""
        try:
            date_str = update.message.text.strip()
            to_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            from_date = context.user_data['from_date']
            
            if to_date < from_date:
                await update.message.reply_text("TO date must be on or after FROM date. Please enter a valid date:")
                return MESS_CUT_TO
            
            context.user_data['to_date'] = to_date
            
            # Show confirmation
            keyboard = [
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_cut")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_cut")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📋 **Confirm Mess Cut**\n\n"
                f"From: {from_date}\n"
                f"To: {to_date}\n"
                f"Duration: {(to_date - from_date).days + 1} days\n\n"
                f"Please confirm your mess cut application:",
                reply_markup=reply_markup
            )
            return MESS_CUT_CONFIRM
            
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
            return MESS_CUT_TO
    
    async def mess_cut_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mess cut confirmation."""
        if update.callback_query.data == "cancel_cut":
            await update.callback_query.edit_message_text(
                "❌ Mess cut application cancelled.\n\nUse /start to return to the main menu."
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        try:
            # Create mess cut record
            mess_cut = MessCut.objects.create(
                student_id=context.user_data['student_id'],
                from_date=context.user_data['from_date'],
                to_date=context.user_data['to_date'],
                applied_by=MessCut.AppliedBy.STUDENT
            )
            
            await update.callback_query.edit_message_text(
                f"✅ **Mess Cut Applied!**\n\n"
                f"From: {mess_cut.from_date}\n"
                f"To: {mess_cut.to_date}\n"
                f"Duration: {(mess_cut.to_date - mess_cut.from_date).days + 1} days\n\n"
                f"Your mess cut has been successfully applied.\n\n"
                f"Use /start to return to the main menu."
            )
            
        except Exception as e:
            logger.error(f"Mess cut creation error: {str(e)}")
            await update.callback_query.edit_message_text(
                "❌ Mess cut application failed. Please try again later or contact support."
            )
        
        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
    
    # QR Code Display
    async def show_qr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show student's QR code."""
        user_id = update.effective_user.id
        
        try:
            student = Student.objects.get(tg_user_id=user_id, status=Student.Status.APPROVED)
            
            # Generate QR code image
            qr_image = QRService.generate_qr_for_student(student)
            
            # Send QR code
            await update.callback_query.answer()
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=qr_image,
                caption=f"🔑 **Your Mess QR Code**\n\n"
                       f"Name: {student.name}\n"
                       f"Roll: {student.roll_no}\n\n"
                       f"📱 This QR is permanent unless admin regenerates all codes.\n"
                       f"🚫 Please don't share with others.\n"
                       f"⏰ Show this during meal times for access."
            )
            
        except Student.DoesNotExist:
            await update.callback_query.answer("You need to be registered and approved first!")
    
    # Admin Functions
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel."""
        user_id = update.effective_user.id
        if user_id not in settings.ADMIN_TG_IDS:
            await update.callback_query.answer("Access denied!")
            return
        
        keyboard = [
            [InlineKeyboardButton("👥 Pending Registrations", callback_data="admin_pending_reg")],
            [InlineKeyboardButton("💳 Review Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("📊 Reports", callback_data="admin_reports")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "⚙️ **Admin Panel**\n\nSelect an option:",
            reply_markup=reply_markup
        )
    
    async def admin_pending_registrations(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending registrations."""
        pending_students = Student.objects.filter(status=Student.Status.PENDING).order_by('created_at')
        
        if not pending_students:
            keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "👥 **Pending Registrations**\n\nNo pending registrations.",
                reply_markup=reply_markup
            )
            return
        
        text = "👥 **Pending Registrations**\n\n"
        keyboard = []
        
        for student in pending_students[:10]:  # Show max 10
            text += f"📝 **{student.name}**\n"
            text += f"Roll: {student.roll_no} | Room: {student.room_no}\n"
            text += f"Phone: {student.phone}\n"
            text += f"Applied: {student.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve {student.roll_no}", callback_data=f"approve_{student.id}"),
                InlineKeyboardButton(f"❌ Deny {student.roll_no}", callback_data=f"deny_{student.id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    
    async def admin_approve_student(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Approve student registration."""
        student_id = update.callback_query.data.split('_')[1]
        
        try:
            student = Student.objects.get(id=student_id, status=Student.Status.PENDING)
            student.status = Student.Status.APPROVED
            student.save()
            
            # Generate QR code and notify student
            QRService.generate_qr_for_student(student)
            await self.notify_student_approved(student)
            
            await update.callback_query.answer(f"✅ {student.name} approved!")
            await self.admin_pending_registrations(update, context)
            
        except Student.DoesNotExist:
            await update.callback_query.answer("Student not found or already processed!")
    
    async def admin_deny_student(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Deny student registration."""
        student_id = update.callback_query.data.split('_')[1]
        
        try:
            student = Student.objects.get(id=student_id, status=Student.Status.PENDING)
            student.status = Student.Status.DENIED
            student.save()
            
            # Notify student
            await self.notify_student_denied(student)
            
            await update.callback_query.answer(f"❌ {student.name} denied!")
            await self.admin_pending_registrations(update, context)
            
        except Student.DoesNotExist:
            await update.callback_query.answer("Student not found or already processed!")
    
    # Notification methods
    async def notify_admins_new_registration(self, student):
        """Notify admins of new registration."""
        message = (
            f"📝 **New Registration**\n\n"
            f"Name: {student.name}\n"
            f"Roll: {student.roll_no}\n"
            f"Room: {student.room_no}\n"
            f"Phone: {student.phone}\n\n"
            f"Use /start to review and approve/deny."
        )
        
        for admin_id in settings.ADMIN_TG_IDS:
            try:
                await self.application.bot.send_message(admin_id, message)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")
    
    async def notify_student_approved(self, student):
        """Notify student of approval."""
        message = (
            f"✅ **Registration Approved!**\n\n"
            f"Congratulations {student.name}! Your mess access is now active.\n\n"
            f"Use /start to access your QR code and other features."
        )
        
        try:
            await self.application.bot.send_message(student.tg_user_id, message)
        except Exception as e:
            logger.error(f"Failed to notify student {student.tg_user_id}: {str(e)}")
    
    async def notify_student_denied(self, student):
        """Notify student of denial."""
        message = (
            f"❌ **Registration Denied**\n\n"
            f"Sorry {student.name}, your registration could not be approved at this time.\n\n"
            f"Please contact the mess admin if you believe this is an error."
        )
        
        try:
            await self.application.bot.send_message(student.tg_user_id, message)
        except Exception as e:
            logger.error(f"Failed to notify student {student.tg_user_id}: {str(e)}")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current conversation."""
        context.user_data.clear()
        await update.message.reply_text("❌ Operation cancelled. Use /start to return to the main menu.")
        return ConversationHandler.END
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again or contact support."
            )
    
    def run_webhook(self, webhook_url):
        """Run bot with webhook."""
        self.application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8000)),
            webhook_url=webhook_url
        )
    
    def run_polling(self):
        """Run bot with polling (for development)."""
        self.application.run_polling()


# Global bot instance
bot_instance = TelegramBot()