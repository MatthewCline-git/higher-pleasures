import logging
from datetime import datetime
from typing import Callable, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db_client.db_client import SQLiteClient

from src.activities.tracker import ActivityTracker
from src.messaging.telegram_onboarder import TelegramOnboarder

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Handles Telegram bot interactions for activity tracking"""

    def __init__(
        self,
        token: str,
        activity_tracker: ActivityTracker,
        db_client: SQLiteClient,
    ):
        """
        Initialize the Telegram handler

        Args:
            token: Telegram bot token
            activity_tracker: ActivityTracker instance
        """
        self.token = token
        self.activity_tracker = activity_tracker
        self.application = Application.builder().token(token).build()
        self.db_client = db_client
        self.onboarder = TelegramOnboarder(db_client)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        if not self._is_user_allowed(update):
            await update.message.reply_text(
                "Welcome to your activity tracker! Send /register to get started."
            )
            return

        await update.message.reply_text(
            "👋 Welcome to your activity tracker!\n\n"
            "Simply send me messages about your activities and I'll track them.\n"
            "For example: 'Read for 30 minutes' or 'Went running for an hour'\n\n"
            "Commands:\n"
            "/help - Show this help message\n"
            "/status - Show your activity status for today"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command"""
        if not self._is_user_allowed(update):
            await update.message.reply_text(
                "You need to register first! Send /register to get started."
            )
            return


        await update.message.reply_text(
            "📝 How to use this bot:\n\n"
            "1. Send me messages about your activities\n"
            "2. Include the duration if possible\n"
            "3. Be as natural as you like\n\n"
            "Examples:\n"
            "- 'Meditated for 20 minutes'\n"
            "- 'Just finished a 5k run'\n"
            "- 'Read War and Peace for 45 mins'\n"
            "- 'Did yoga this morning'"
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /status command"""
        if not self._is_user_allowed(update):
            await update.message.reply_text(
                "You need to register first! Send /register to get started."
            )
            return


        # TODO: Implement status retrieval from sheets
        await update.message.reply_text(
            "🎯 Today's activities:\n(Status feature coming soon!)"
        )

    async def track_activity(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming activity messages"""
        user_id = update.effective_user.id
        if not self.db_client.is_user_allowed(user_id):
            print(f"User {user_id} not in allowed users:")
            if update.effective_chat.type == "private":
                await update.message.reply_text(
                    "❌ You don't have a configured habit tracker. Send '/register' to get started."
                )
            return

        message_text = update.message.text

        # For group chats, only process messages that mention the bot
        if update.effective_chat.type in ["group", "supergroup"]:
            print("Processing group chat message")
            if update.message.entities:
                bot_mentioned = False
                for entity in update.message.entities:
                    if entity.type == "mention":
                        mention = message_text[
                            entity.offset : entity.offset + entity.length
                        ]
                        print(f"Found mention: {mention}")
                        print(f"Bot username: @{context.bot.username}")
                        if mention == f"@{context.bot.username}":
                            bot_mentioned = True
                            message_text = message_text.replace(mention, "").strip()
                            break

                if not bot_mentioned:
                    print("Bot not mentioned, ignoring message")
                    return
            else:
                print("No entities in message, ignoring")
                return

        try:
            print(f"Processing activity: {message_text}")
            self.activity_tracker.track_activity(user_id=user_id, message=message_text)
            await update.message.reply_text("✅ Activity tracked!")

        except Exception as e:
            logger.error(f"Error tracking activity: {e}")
            print(f"Error tracking activity: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't track that activity. Please try again."
            )

    def _is_user_allowed(self, update: Update) -> bool:
        """Check if the user is allowed to use the bot"""
        user_id = update.effective_user.id
        return self.db_client.is_user_allowed(user_id)

    def start_polling(self) -> None:
        """Start the bot polling for messages"""
        print("Starting bot...")

        # Register handlers with modified filters
        self.application.add_handler(self.onboarder.get_conversation_handler())
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))

        # Add handler for both private and group messages
        self.application.add_handler(
            MessageHandler(
                (
                    filters.TEXT
                    & ~filters.COMMAND
                    & (filters.ChatType.GROUPS | filters.ChatType.PRIVATE)
                ),
                self.track_activity,
            )
        )

        print("Handlers registered, starting polling...")
        self.application.run_polling()
