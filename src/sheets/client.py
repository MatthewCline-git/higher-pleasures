import logging
from datetime import datetime, timedelta
from typing import Generator, List, Optional, Tuple

from google.api_core import retry
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .models import EntryType

logger = logging.getLogger(__name__)


class SheetError(Exception):
    """Custom exception for sheet-related errors"""

    pass


class GoogleSheetsClient:
    """Handles all Google Sheets operations"""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    BATCH_SIZE = 50

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str,
    ):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.service = self._build_sheets_service()

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

    def initialize_year_structure(
        self, sheet_name:str, year: Optional[int] = None, force: bool = False
    ) -> None:
        """Initialize the spreadsheet with all weeks and days of the year."""
        year = year or datetime.now().year
        logger.info(f"Initializing year structure for {year}")

        if not force:
            current_dates = self.get_current_dates(sheet_name=sheet_name)
            date_gen = self._generate_dates(year)
            expected_dates = [date_str for _, date_str in date_gen]

            if self._validate_current_structure(current_dates, expected_dates):
                logger.info("Sheet is already properly initialized")
                return

        self._perform_initialization(sheet_name, year)

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
    def get_current_dates(self, sheet_name: str) -> List[str]:
        """Get the current content of column A with retry logic"""
        range_name = f"{sheet_name}!A:A"
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
    def clear_sheet(self, sheet_name) -> None:
        """Clear all content from sheet with retry logic"""
        clear_range = f"{sheet_name}!A1:Z1000"
        try:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id, body={"ranges": [clear_range]}
            ).execute()
        except Exception as e:
            logger.error(f"Error clearing sheet: {e}")
            raise SheetError(f"Failed to clear sheet: {str(e)}")

    def _validate_current_structure(
        self, current: List[str], expected: List[str]
    ) -> bool:
        """Validate if current sheet structure matches expected structure"""
        return len(current) == len(expected) and all(
            curr == exp for curr, exp in zip(current, expected)
        )

    def _perform_initialization(self, sheet_name: str, year: int) -> None:
        """Perform the actual initialization of the sheet"""
        logger.info("Starting sheet initialization")
        self.clear_sheet(sheet_name=sheet_name)
        self.update_header_row(sheet_name=sheet_name)

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
    def append_to_sheet_formatted(self, sheet_name: str, values: List[List[str]]) -> None:
        """Append rows to the sheet with retry logic"""
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
        except Exception as e:
            logger.error(f"Error appending to sheet: {e}")
            raise SheetError(f"Failed to append to sheet: {str(e)}")

    @retry.Retry()
    def get_date_row_index(self, sheet_name: str, date: datetime) -> Optional[int]:
        """Find the row index for a given date"""
        date_str = date.strftime("%A, %B %d")
        range_name = f"{sheet_name}!A:A"
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
    def get_row_values(self, sheet_name: str, row_index: int) -> List[float]:
        """Get all values for a specific row"""
        range_name = f"{sheet_name}!{row_index}:{row_index}"
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
    def update_row(self, sheet_name: str, row_index: int, values: List[float]) -> None:
        """Update an entire row with new values"""
        range_name = (
            f"{sheet_name}!A{row_index}:{chr(65 + len(values))}{row_index}"
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
    def update_header_row(self, sheet_name: str, activities: Optional[List[str]] = None) -> None:
        """Update the header row with given activities"""
        activities = activities or []
        header_row = ["Date"] + activities
        range_name = f"{sheet_name}!A1:{chr(65 + len(header_row))}{1}"

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

    def update_activities_header(self, sheet_name, activity: str) -> None:
        """Add a new activity column if it doesn't exist"""
        existing_activities = self.get_activity_columns(sheet_name=sheet_name)
        if activity not in existing_activities:
            logger.info(f"Adding new activity column: {activity}")
            activities = existing_activities + [activity]
            self.update_header_row(activities)

    @retry.Retry()
    def get_activity_columns(self, sheet_name: str) -> List[str]:
        """Get list of activity names from the header row"""
        range_name = f"{sheet_name}!A1:Z1"

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
