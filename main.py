# src/main.py
import os

from dotenv import load_dotenv

from src.activities.parser import OpenAIActivityParser
from src.activities.tracker import ActivityTracker
from src.sheets.client import GoogleSheetsClient


def load_config():
    """Load configuration from environment variables"""
    load_dotenv()

    required_vars = {
        "SPREADSHEET_ID": os.getenv("SPREADSHEET_ID"),
        "SHEET_NAME": os.getenv("SHEET_NAME"),
        "CREDENTIALS_PATH": os.getenv("CREDENTIALS_PATH"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
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

    # Initialize components
    sheets_client = GoogleSheetsClient(
        spreadsheet_id=config["SPREADSHEET_ID"],
        sheet_name=config["SHEET_NAME"],
        credentials_path=config["CREDENTIALS_PATH"],
    )

    sheets_client.initialize_year_structure()

    activity_parser = OpenAIActivityParser(
        api_key=config["OPENAI_API_KEY"], confidence_threshold=0.7
    )

    # Initialize tracker
    tracker = ActivityTracker(sheets_client, activity_parser)

    # Example usage
    tracker.track_activity("Cranked out the last chapter of the Sound and the Fury")


if __name__ == "__main__":
    main()
