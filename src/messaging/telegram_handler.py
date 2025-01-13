import logging
from datetime import datetime
from typing import Optional, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from ..activities.tracker import ActivityTracker

logger = logging.getLogger(__name__)

class TelegramHandler:
    """Handles Telegram bot interactions for activity tracking"""
    
    def __init__(
        self, 
        token: str,
        activity_tracker: ActivityTracker,
        allowed_user_ids: Optional[list[int]] = None
    ):
        """
        Initialize the Telegram handler
        
        Args:
            token: Telegram bot token
            activity_tracker: ActivityTracker instance
            allowed_user_ids: List of Telegram user IDs that can use the bot
        """
        self.token = token
        self.activity_tracker = activity_tracker
        self.allowed_user_ids = allowed_user_ids or []
        self.application = Application.builder().token(token).build()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        if not self._is_user_allowed(update):
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
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
            return
            
        # TODO: Implement status retrieval from sheets
        await update.message.reply_text(
            "🎯 Today's activities:\n"
            "(Status feature coming soon!)"
        )

    async def track_activity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming activity messages"""
        if not self._is_user_allowed(update):
            return

        user_id = update.effective_user.id
        if user_id not in self.allowed_user_ids:
            await update.message.reply_text("❌ You don't have a configured habit tracker.")
            return
        
        message_text = update.message.text
        try:
            self.activity_tracker.track_activity(user_id=user_id, message=message_text)
            await update.message.reply_text("✅ Activity tracked!")
            
        except Exception as e:
            logger.error(f"Error tracking activity: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't track that activity. Please try again."
            )

    def _is_user_allowed(self, update: Update) -> bool:
        """Check if the user is allowed to use the bot"""
        if not self.allowed_user_ids:
            return True
        return update.effective_user.id in self.allowed_user_ids

    def start_polling(self) -> None:
        """Start the bot polling for messages"""
        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.track_activity)
        )

        # Start polling
        self.application.run_polling()