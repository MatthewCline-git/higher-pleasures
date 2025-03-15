import logging
import os
from typing import TypedDict

from dotenv import load_dotenv

from src.activities.parser import OpenAIActivityParser
from src.activities.tracker import ActivityTracker
from src.db.postgres_client import PostgresClient
from src.logging_config.logging_config import setup_logging
from src.messaging.telegram_handler import TelegramHandler
from src.sheets.client import GoogleSheetsClient


class AppConfig(TypedDict):
    """Configuration for the application"""

    SPREADSHEET_ID: str
    FRIEND_SHEET_NAME: str
    MY_SHEET_NAME: str
    FRIEND_TELEGRAM_ID: str
    MY_TELEGRAM_ID: str
    OPENAI_API_KEY: str
    TELEGRAM_BOT_API_KEY: str
    GOOGLE_CREDENTIALS: str
    POSTGRES_URL: str


def load_config() -> AppConfig:
    """Load configuration from environment variables"""
    load_dotenv()

    required_vars = {
        "SPREADSHEET_ID": os.getenv("SPREADSHEET_ID"),
        "FRIEND_SHEET_NAME": os.getenv("FRIEND_SHEET_NAME"),
        "MY_SHEET_NAME": os.getenv("MY_SHEET_NAME"),
        "FRIEND_TELEGRAM_ID": os.getenv("FRIEND_TELEGRAM_ID"),
        "MY_TELEGRAM_ID": os.getenv("MY_TELEGRAM_ID"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "TELEGRAM_BOT_API_KEY": os.getenv("TELEGRAM_TEST_BOT_API_KEY") or os.getenv("TELEGRAM_BOT_API_KEY"),
        "GOOGLE_CREDENTIALS": os.getenv("GOOGLE_CREDENTIALS"),
        "POSTGRES_URL": os.getenv("PROD_POSTGRES_URL") or os.getenv("DEV_POSTGRES_URL"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        raise OSError(f"Missing required environment variables: {', '.join(missing)}")

    # We've verified all values exist, so we can cast to the TypedDict
    # which has no None values
    return required_vars


# ruff: noqa: D103
def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Higher Pleasures Bot")

    config = load_config()
    user_sheet_mapping = {
        int(config["FRIEND_TELEGRAM_ID"]): config["FRIEND_SHEET_NAME"],
        int(config["MY_TELEGRAM_ID"]): config["MY_SHEET_NAME"],
    }

    # Initialize components
    sheets_client = GoogleSheetsClient(
        spreadsheet_id=config["SPREADSHEET_ID"],
    )

    db_client = PostgresClient()

    activity_parser = OpenAIActivityParser(api_key=config["OPENAI_API_KEY"], confidence_threshold=0.7)

    tracker = ActivityTracker(
        sheets_client=sheets_client,
        activity_parser=activity_parser,
        user_sheet_mapping=user_sheet_mapping,
        db_client=db_client,
    )

    telegram_handler = TelegramHandler(
        token=config["TELEGRAM_BOT_API_KEY"],
        activity_tracker=tracker,
        db_client=db_client,
    )

    logger.info("🤖 Starting Telegram bot...")
    telegram_handler.start_polling()


if __name__ == "__main__":
    main()
