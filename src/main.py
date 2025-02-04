# src/main.py
import os

from dotenv import load_dotenv

from src.activities.parser import OpenAIActivityParser
from src.activities.tracker import ActivityTracker
from src.messaging.telegram_handler import TelegramHandler
from src.sheets.client import GoogleSheetsClient


def load_config():
    """Load configuration from environment variables"""
    load_dotenv()

    required_vars = {
        "SPREADSHEET_ID": os.getenv("SPREADSHEET_ID"),
        "FRIEND_SHEET_NAME": os.getenv("FRIEND_SHEET_NAME"),
        "MY_SHEET_NAME": os.getenv("MY_SHEET_NAME"),
        "FRIEND_TELEGRAM_ID": os.getenv("FRIEND_TELEGRAM_ID"),
        "MY_TELEGRAM_ID": os.getenv("MY_TELEGRAM_ID"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "TELEGRAM_BOT_API_KEY": os.getenv("TELEGRAM_BOT_API_KEY"),
        "GOOGLE_CREDENTIALS": os.getenv("GOOGLE_CREDENTIALS"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return required_vars


def main():
    # Load configuration
    config = load_config()

    user_sheet_mapping = {
        int(config["FRIEND_TELEGRAM_ID"]): config["FRIEND_SHEET_NAME"],
        int(config["MY_TELEGRAM_ID"]): config["MY_SHEET_NAME"],
    }

    # Initialize components
    sheets_client = GoogleSheetsClient(
        spreadsheet_id=config["SPREADSHEET_ID"],
    )

    activity_parser = OpenAIActivityParser(
        api_key=config["OPENAI_API_KEY"], confidence_threshold=0.7
    )

    tracker = ActivityTracker(
        sheets_client=sheets_client,
        activity_parser=activity_parser,
        user_sheet_mapping=user_sheet_mapping,
    )

    telegram_handler = TelegramHandler(
        token=config["TELEGRAM_BOT_API_KEY"],
        activity_tracker=tracker,
        allowed_user_ids=list(user_sheet_mapping.keys()),
    )

    print("🤖 Starting Telegram bot...")
    telegram_handler.start_polling()


if __name__ == "__main__":
    main()
