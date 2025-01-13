import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import get_close_matches
from enum import Enum
from typing import Generator, List, Optional, Tuple

from dotenv import load_dotenv
from google.api_core import retry
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SheetError(Exception):
    """Custom exception for sheet-related errors"""

    pass


@dataclass
class SheetEntry:
    """Represents a single row entry in the activity sheet"""

    date: datetime
    values: List[float]


class EntryType(Enum):
    """Types of entries that can appear in the date column"""

    WEEK_HEADER = "WEEK"
    DATE = "DATE"


class ActivityTracker:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    BATCH_SIZE = 50

    def __init__(
        self,
        credentials_path: str | None = None,
        spreadsheet_id: str | None = None,
        sheet_name: str | None = None,
        openai_api_key: str | None = None,
        confidence_threshold: float = 0.7,
    ):
        """Initialize the ActivityTracker with required credentials and sheet info"""

        load_dotenv()

        SPREADSHEET_ID = spreadsheet_id or os.getenv("SPREADSHEET_ID")
        SHEET_NAME = sheet_name or os.getenv("SHEET_NAME")
        CREDENTIALS_PATH = credentials_path or os.getenv("CREDENTIALS_PATH")
        OPENAI_API_KEY = openai_api_key or os.getenv("OPENAI_API_KEY")

        if not all([SPREADSHEET_ID, SHEET_NAME, CREDENTIALS_PATH, OPENAI_API_KEY]):
            raise EnvironmentError("Missing required environment variables")

        self.spreadsheet_id = SPREADSHEET_ID
        self.sheet_name = SHEET_NAME
        self.credentials_path = CREDENTIALS_PATH
        self.service = self._build_sheets_service()
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.confidence_threshold = confidence_threshold

    def _generate_system_prompt(self) -> str:
        return f"""Extract activity and duration from the message. 
Existing activity categories are: {", ".join(self.get_activity_columns())}

If the described activity closely matches an existing category, use that category.
Always convert duration to hours (e.g., 30 minutes = 0.5 hours). If there is no concrete duration number in the input, estimate.

Examples:
Input: "Went for a run this morning for 30 minutes"
Response: {{
    "activity": "Running",
    "duration": 0.5,
    "confidence": 1.0,
    "matched_category": "Running"
}}

Input: "Did some weightlifting for an hour and a half"
Response: {{
    "activity": "Working out",
    "duration": 1.5,
    "confidence": 0.9,
    "matched_category": "Working out"
}}

Input: "Read War and Peace for 45 mins"
Response: {{
    "activity": "Reading",
    "duration": 0.75,
    "confidence": 1.0,
    "matched_category": "Reading"
}}

Input: "Practiced guitar for two hours"
Response: {{
    "activity": "Guitar",
    "duration": 2.0,
    "confidence": 0.2,
    "matched_category": null
}}

Input: "Meditated before bed for twenty minutes"
Response: {{
    "activity": "Meditation",
    "duration": 0.33,
    "confidence": 0.95,
    "matched_category": "Meditation"
}}

Input: "Did calisthenics in the park this afternoon"
Response: {{
    "activity": "Calisthenics",
    "duration": 1.0,
    "confidence": 0.9,
    "matched_category": "Working out"
}}

Return JSON with:
- activity: The activity name (use matched_category if confidence > {self.confidence_threshold})
- duration: Duration in hours (convert minutes to decimal hours)
- confidence: How confident (0-1) this matches an existing category
- matched_category: The existing category it matches, if any"""

    def parse_message(self, message: str) -> dict:
        """Parse a natural language message into activity and duration"""
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self._generate_system_prompt()},
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        if (
            result.get("matched_category")
            and result.get("confidence", 0) > self.confidence_threshold
        ):
            result["activity"] = result["matched_category"]

        return {
            "activity": result["activity"],
            "duration": result["duration"],
        }

    def _build_sheets_service(self):
        """Create and return an authorized Sheets API service object"""
        try:
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=self.SCOPES
            )
            return build("sheets", "v4", credentials=creds)
        except Exception as e:
            logger.error(f"Failed to build sheets service: {e}")
            raise SheetError(f"Could not initialize sheets service: {str(e)}")

    def _generate_dates(
        self, year: int
    ) -> Generator[Tuple[EntryType, str], None, None]:
        """Generate sequence of dates and week headers for the year"""
        current_date = datetime(year, 1, 1)
        current_week = None

        while current_date.year == year:
            week_number = current_date.isocalendar()[1]

            if week_number != current_week:
                yield EntryType.WEEK_HEADER, f"Week {week_number}"
                current_week = week_number

            yield EntryType.DATE, current_date.strftime("%A, %B %-d")
            current_date += timedelta(days=1)

    @retry.Retry()
    def get_current_dates(self) -> List[str]:
        """Get the current content of column A with retry logic"""
        range_name = f"{self.sheet_name}!A:A"
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
            return [row[0] for row in result.get("values", [])[1:] if row]
        except Exception as e:
            logger.error(f"Error reading current dates: {e}")
            raise SheetError(f"Failed to read current dates: {str(e)}")

    @retry.Retry()
    def clear_sheet(self) -> None:
        """Clear all content from sheet with retry logic"""
        clear_range = f"{self.sheet_name}!A1:Z1000"
        try:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id, body={"ranges": [clear_range]}
            ).execute()
        except Exception as e:
            logger.error(f"Error clearing sheet: {e}")
            raise SheetError(f"Failed to clear sheet: {str(e)}")

    def initialize_year_structure(
        self, year: Optional[int] = None, force: bool = False
    ) -> None:
        """Initialize the spreadsheet with all weeks and days of the year."""
        year = year or datetime.now().year
        logger.info(f"Initializing year structure for {year}")

        if not force:
            current_dates = self.get_current_dates()
            date_gen = self._generate_dates(year)
            expected_dates = [date_str for _, date_str in date_gen]

            if self._validate_current_structure(current_dates, expected_dates):
                logger.info("Sheet is already properly initialized")
                return

        self._perform_initialization(year)

    def _validate_current_structure(
        self, current: List[str], expected: List[str]
    ) -> bool:
        """Validate if current sheet structure matches expected structure"""
        return len(current) == len(expected) and all(
            curr == exp for curr, exp in zip(current, expected)
        )

    def _perform_initialization(self, year: int) -> None:
        """Perform the actual initialization of the sheet"""
        logger.info("Starting sheet initialization")
        self.clear_sheet()
        self.update_header_row()

        batch = []
        for entry_type, value in self._generate_dates(year):
            batch.append([value])

            if len(batch) >= self.BATCH_SIZE:
                self.append_to_sheet_formatted(batch)
                batch = []

        if batch:  # Don't forget remaining entries
            self.append_to_sheet_formatted(batch)

        logger.info("Sheet initialization completed successfully")

    @retry.Retry()
    def append_to_sheet_formatted(self, values: List[List[str]]) -> None:
        """Append rows to the sheet with retry logic"""
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
        except Exception as e:
            logger.error(f"Error appending to sheet: {e}")
            raise SheetError(f"Failed to append to sheet: {str(e)}")

    @retry.Retry()
    def get_date_row_index(self, date: datetime) -> Optional[int]:
        """Find the row index for a given date"""
        date_str = date.strftime("%A, %B %d")
        range_name = f"{self.sheet_name}!A:A"
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            if "values" in result:
                for i, row in enumerate(result["values"]):
                    if row and row[0] == date_str:
                        return i + 1
            return None
        except Exception as e:
            logger.error(f"Error finding date row: {e}")
            raise SheetError(f"Failed to find row for date {date_str}: {str(e)}")

    @retry.Retry()
    def get_row_values(self, row_index: int) -> List[float]:
        """Get all values for a specific row"""
        range_name = f"{self.sheet_name}!{row_index}:{row_index}"
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [[]])[0] if "values" in result else []
        except Exception as e:
            logger.error(f"Error reading row values: {e}")
            raise SheetError(f"Failed to read row {row_index}: {str(e)}")

    @retry.Retry()
    def update_row(self, row_index: int, values: List[float]) -> None:
        """Update an entire row with new values"""
        range_name = (
            f"{self.sheet_name}!A{row_index}:{chr(65 + len(values))}{row_index}"
        )
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [values]},
            ).execute()
        except Exception as e:
            logger.error(f"Error updating row: {e}")
            raise SheetError(f"Failed to update row {row_index}: {str(e)}")

    def process_new_entry(self, date: datetime, activity: str, duration: float) -> None:
        """Process a new activity entry with validation"""
        if duration < 0:
            raise ValueError("Duration cannot be negative")

        logger.info(
            f"Processing new entry: {activity} for {date.date()} - {duration} hours"
        )

        self.update_activities_header(activity)
        date_row_index = self.get_date_row_index(date)

        if not date_row_index:
            raise ValueError(f"Could not find row for date: {date}")

        self._update_activity_duration(date_row_index, activity, duration)

    def _update_activity_duration(
        self, row_index: int, activity: str, duration: float
    ) -> None:
        """Update the duration for a specific activity"""
        current_values = self.get_row_values(row_index)
        activities = self.get_activity_columns()
        activity_index = activities.index(activity) + 1

        current_values = self._ensure_row_length(current_values, activity_index)
        current_duration = float(current_values[activity_index] or 0)
        current_values[activity_index] = current_duration + duration

        self.update_row(row_index, current_values)

    @staticmethod
    def _ensure_row_length(values: List[float], required_length: int) -> List[float]:
        """Ensure the row has the required length, padding with zeros if needed"""
        return values + [0] * (required_length + 1 - len(values))

    @retry.Retry()
    def update_header_row(self, activities: Optional[List[str]] = None) -> None:
        """Update the header row with given activities"""
        activities = activities or []
        header_row = ["Date"] + activities
        range_name = f"{self.sheet_name}!A1:{chr(65 + len(header_row))}{1}"

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [header_row]},
            ).execute()
        except Exception as e:
            logger.error(f"Error updating header row: {e}")
            raise SheetError(f"Failed to update header row: {str(e)}")

    def update_activities_header(self, activity: str) -> None:
        """Add a new activity column if it doesn't exist"""
        existing_activities = self.get_activity_columns()
        if activity not in existing_activities:
            logger.info(f"Adding new activity column: {activity}")
            activities = existing_activities + [activity]
            self.update_header_row(activities)

    @retry.Retry()
    def get_activity_columns(self) -> List[str]:
        """Get list of activity names from the header row"""
        range_name = f"{self.sheet_name}!A1:Z1"

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            if "values" in result and result["values"]:
                headers = result["values"][0]
                return headers[1:] if len(headers) > 1 else []
            return []

        except Exception as e:
            logger.error(f"Error reading headers: {e}")
            raise SheetError(f"Failed to read activity columns: {str(e)}")


if __name__ == "__main__":
    tracker = ActivityTracker()
    tracker.initialize_year_structure()

    result = tracker.parse_message("Did laps in the pool from 10am to noon")
    tracker.process_new_entry(
        date=datetime.now() + timedelta(days=2),
        activity=result["activity"],
        duration=result["duration"],
    )
