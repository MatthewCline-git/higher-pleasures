import logging
import re
import uuid
from dataclasses import dataclass
from enum import Enum, auto

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.db.client import SQLiteClient


logger = logging.getLogger(__name__)


class OnboardingState(Enum):
    AWAITING_FULL_NAME = auto()
    AWAITING_EMAIL = auto()
    AWAITING_CELL = auto()
    AWAITING_CONFIRMATION = auto()
    CONFIRMING_INFO = auto()


@dataclass
class UserRegistrationData:
    telegram_user_id: int
    first_name: str = ""
    last_name: str = ""
    email: str | None = None
    cell: str = ""


class TelegramOnboarder:
    def __init__(self, db_client: SQLiteClient) -> None:
        self.db_client = db_client
        self.temp_user_data: dict[int, UserRegistrationData] = {}

    def parse_full_name(self, full_name: str) -> tuple[bool, str, tuple[str, str] | None]:
        """
        Parse full name into first and last name.

        Returns: (is_valid, error_message, (first_name, last_name))
        """
        # Remove extra whitespace and split
        parts = [p for p in full_name.strip().split() if p]

        if len(parts) < 2:
            return False, "Please enter both your first and last name.", None

        if len(parts) > 6:  # Arbitrary reasonable limit
            return (
                False,
                "The name you entered is too long. Please enter just your first and last name.",
                None,
            )

        # If more than 2 parts, first part is first name, last part is last name
        first_name = parts[0]
        last_name = " ".join(parts[1:])

        return True, "", (first_name, last_name)

    def get_conversation_handler(self) -> ConversationHandler:
        """Return the conversation handler for the onboarding process"""
        return ConversationHandler(
            entry_points=[CommandHandler("register", self.start_registration)],
            states={
                OnboardingState.AWAITING_FULL_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_full_name)
                ],
                OnboardingState.AWAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_email)],
                OnboardingState.AWAITING_CELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_cell)],
                OnboardingState.AWAITING_CONFIRMATION: [
                    CallbackQueryHandler(self.handle_confirmation, pattern="^(confirm|restart)$")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_registration)],
        )

    async def start_registration(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Start the registration process"""
        user_id = update.effective_user.id
        self.temp_user_data[user_id] = UserRegistrationData(telegram_user_id=user_id)

        await update.message.reply_text(
            "👋 Welcome to the Activity Tracker! Let's get you set up.\n\n"
            "What's your name? (first and last)\n\n"
            "(Use /cancel at any time to stop the registration process)"
        )
        return OnboardingState.AWAITING_FULL_NAME

    async def handle_full_name(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle the full name input"""
        user_id = update.effective_user.id
        full_name = update.message.text.strip()

        is_valid, error_msg, names = self.parse_full_name(full_name)
        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}")
            return OnboardingState.AWAITING_FULL_NAME

        first_name, last_name = names
        self.temp_user_data[user_id].first_name = first_name
        self.temp_user_data[user_id].last_name = last_name

        await update.message.reply_text("Thanks! What's your email? (optional - you can type 'skip' to continue)")
        return OnboardingState.AWAITING_EMAIL

    async def handle_email(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
        """Handle email input"""
        user_id = update.effective_user.id
        email = update.message.text.strip()

        if email.lower() != "skip":
            self.temp_user_data[user_id].email = email

        await update.message.reply_text("Almost done! Last thing, please provide your cell number.\n")
        return OnboardingState.AWAITING_CELL

    def validate_and_format_us_phone(self, phone: str) -> tuple[bool, str, str | None]:
        """
        Validate and formats a US phone number.

        Returns: (is_valid, error_message, formatted_number)
        Formatted number will be in E.164 format: +1XXXXXXXXXX
        """
        # Remove all non-numeric characters
        digits = re.sub(r"\D", "", phone)

        # Handle country code if provided
        digits = digits.removeprefix("1")

        # Check if we have exactly 10 digits
        # ruff: noqa: PLR2004
        if len(digits) != 10:
            return False, "Please enter a valid 10-digit US phone number.", None

        # Basic area code validation (can be expanded)
        area_code = digits[:3]
        if area_code.startswith(("0", "1")):
            return False, "Invalid area code.", None

        # Format to E.164
        formatted = f"+1{digits}"
        return True, "", formatted

    async def handle_cell(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> OnboardingState:
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

    async def handle_confirmation(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> int:
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
            except Exception:
                logger.exception(f"Error saving user data. \n\n{user_data=}")
                await query.edit_message_text(
                    "❌ Sorry, there was an error saving your information. Please try registering again with /register"
                )
            finally:
                del self.temp_user_data[telegram_user_id]

        else:
            await query.edit_message_text("No problem! Let's start over. Use /register when you're ready.")
            del self.temp_user_data[telegram_user_id]

        return ConversationHandler.END

    async def cancel_registration(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the registration process"""
        telegram_user_id = update.effective_user.id
        if telegram_user_id in self.temp_user_data:
            del self.temp_user_data[telegram_user_id]

        await update.message.reply_text("🚫 Registration cancelled. Use /register to start over.")
        return ConversationHandler.END
