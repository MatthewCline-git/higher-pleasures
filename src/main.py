# src/main.py
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from .activities.parser import OpenAIActivityParser
from .activities.tracker import ActivityTracker
from .sheets.client import GoogleSheetsClient


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

    activity_parser = OpenAIActivityParser(
        api_key=config["OPENAI_API_KEY"], confidence_threshold=0.7
    )

    # Initialize tracker
    tracker = ActivityTracker(sheets_client, activity_parser)

    # Initialize sheet structure if needed
    tracker.initialize_year_structure()

    # Example usage
    tracker.track_activity("Did laps in the pool from 10am to noon")


if __name__ == "__main__":
    main()
