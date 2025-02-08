from dataclasses import dataclass
from enum import Enum, auto
import re
from typing import Dict, Optional, Tuple
from db_client.db_client import SQLiteClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters
import uuid
import logging

logger = logging.getLogger(__name__)

class OnboardingState(Enum):
    AWAITING_FIRST_NAME = auto()
    AWAITING_LAST_NAME = auto()
    AWAITING_EMAIL = auto()
    AWAITING_CELL = auto()
    AWAITING_CONFIRMATION = auto()
    CONFIRMING_INFO = auto()

@dataclass
class UserRegistrationData:
    telegram_user_id: int
    first_name: str = ""
    last_name: str = ""
    email: Optional[str] = None
    cell: str = ""

class TelegramOnboarder:
    def __init__(self, db_client: SQLiteClient):
        self.db_client = db_client
        self.temp_user_data: Dict[int, UserRegistrationData] = {}
    
    def get_conversation_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler("register", self.start_registration)],
            states={
                OnboardingState.AWAITING_FIRST_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_first_name)
                ],
                OnboardingState.AWAITING_LAST_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_last_name)
                ],
                OnboardingState.AWAITING_EMAIL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_email)
                ],
                OnboardingState.AWAITING_CELL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_cell)
                ],
                OnboardingState.AWAITING_CONFIRMATION: [
                    CallbackQueryHandler(self.handle_confirmation, pattern="^(confirm|restart)$")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_registration)],
        )
    
    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Start the registration process"""
        user_id = update.effective_user.id
        self.temp_user_data[user_id] = UserRegistrationData(telegram_user_id=str(user_id))

        await update.message.reply_text(
            "👋 Welcome to the Activity Tracker! Let's get you set up.\n\n"
            "What's your first name?\n\n"
            "(Use /cancel at any time to stop the registration process)"
        )
        return OnboardingState.AWAITING_FIRST_NAME
    
    async def handle_first_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle the first name input"""
        user_id = update.effective_user.id
        first_name = update.message.text.strip()

        self.temp_user_data[user_id].first_name = first_name

        await update.message.reply_text("Great! Now, what's your last name?")
        return OnboardingState.AWAITING_LAST_NAME
    
    async def handle_last_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle the last name input"""
        user_id = update.effective_user.id
        last_name = update.message.text.strip()

        self.temp_user_data[user_id].last_name = last_name

        await update.message.reply_text(
            "Thanks! Please share your email address (optional - you can type 'skip' to continue)"
        )
        return OnboardingState.AWAITING_EMAIL
    
    async def handle_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle email input"""
        user_id = update.effective_user.id
        email = update.message.text.strip()
        
        if email.lower() != "skip":
            self.temp_user_data[user_id].email = email
        
        await update.message.reply_text(
            "Almost done! Last thing, please provide your cell number.\n"
        )
        return OnboardingState.AWAITING_CELL
    
    def validate_and_format_us_phone(self, phone: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validates and formats a US phone number.
        Returns: (is_valid, error_message, formatted_number)
        Formatted number will be in E.164 format: +1XXXXXXXXXX
        """
        # Remove all non-numeric characters
        digits = re.sub(r'\D', '', phone)
        
        # Handle country code if provided
        if digits.startswith('1'):
            digits = digits[1:]
        
        # Check if we have exactly 10 digits
        if len(digits) != 10:
            return False, "Please enter a valid 10-digit US phone number.", None
            
        # Basic area code validation (can be expanded)
        area_code = digits[:3]
        if area_code.startswith('0') or area_code.startswith('1'):
            return False, "Invalid area code.", None
            
        # Format to E.164
        formatted = f"+1{digits}"
        return True, "", formatted
    
    async def handle_cell(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle cell input"""
        user_id = update.effective_user.id
        cell = update.message.text.strip()
        is_valid, error_msg, formatted_number = self.validate_and_format_us_phone(cell)

        if not is_valid:
            await update.message.reply_text(
                f"❌ {error_msg}\n\n"
                "Please enter your phone number in any standard US format:\n"
                "(555) 123-4567\n"
                "555-123-4567\n"
                "5551234567"
            )
            return OnboardingState.AWAITING_CELL

        self.temp_user_data[user_id].cell = cell

        user_data = self.temp_user_data[user_id]
        confirmation_text = (
            "📋 Please confirm your information:\n\n"
            f"First Name: {user_data.first_name}\n"
            f"Last Name: {user_data.last_name}\n"
            f"Email: {user_data.email or 'Not provided'}\n"
            f"Phone: {user_data.cell}\n\n"
            "Is this correct?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, save it!", callback_data="confirm"),
                InlineKeyboardButton("❌ No, start over", callback_data="restart"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
        return OnboardingState.AWAITING_CONFIRMATION
    
    async def handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle user's confirmation of their information"""
        query = update.callback_query
        await query.answer()  # Acknowledge the button click
        telegram_user_id = query.from_user.id  # Get user ID from the query
        if query.data == "confirm":
            try:
                # Save user data to the database
                user_data = self.temp_user_data[telegram_user_id]
                self.db_client.insert_user(
                    user_id=uuid.uuid4().hex,
                    first_name=user_data.first_name,
                    last_name=user_data.last_name,
                    cell=user_data.cell,
                    telegram_id=telegram_user_id,
                    email=user_data.email,
                )
                
                await query.edit_message_text(
                    "✨ Perfect! You're all set up and ready to start tracking activities!\n\n"
                    "Try sending me a message like:\n"
                    "- 'Went running for 30 minutes'\n"
                    "- 'Read for an hour yesterday'\n"
                    "- 'Meditated this morning for 20 mins'\n\n"
                    "Type /help anytime to see more examples!"
                )
            except Exception as e:
                logger.error(f"Error saving user data: {e}\n\n{user_data=}")
                await query.edit_message_text(
                    "❌ Sorry, there was an error saving your information. "
                    "Please try registering again with /register"
                )
            finally:
                del self.temp_user_data[telegram_user_id]

        else:
            await query.edit_message_text(
                "No problem! Let's start over. Use /register when you're ready."
            )
            del self.temp_user_data[telegram_user_id]

        return ConversationHandler.END
    
    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the registration process"""
        telegram_user_id = update.effective_user.id
        if telegram_user_id in self.temp_user_data:
            del self.temp_user_data[telegram_user_id]

        await update.message.reply_text(
            "🚫 Registration cancelled. Use /register to start over."
        )
        return ConversationHandler.END