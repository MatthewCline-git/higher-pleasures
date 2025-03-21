import json
import logging
import os
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar

from google.api_core import retry
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .models import EntryType


logger = logging.getLogger(__name__)


class SheetError(Exception):
    """Custom exception for sheet-related errors"""


class GoogleSheetsClient:
    """Handles all Google Sheets operations"""

    SCOPES: ClassVar = ["https://www.googleapis.com/auth/spreadsheets"]
    BATCH_SIZE = 50

    def __init__(
        self,
        spreadsheet_id: str,
    ) -> None:
        """
        Initialize the SheetsClient with the given spreadsheet ID.

        Args:
            spreadsheet_id (str): The ID of the spreadsheet to interact with.

        """
        self.spreadsheet_id = spreadsheet_id
        self.service = self._build_sheets_service()

    def _load_google_credentials(self):
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS environment variable not found")
        return creds_json

    def _get_google_credentials(self):
        try:
            creds_json = self._load_google_credentials()
            creds_dict = json.loads(creds_json)
            return service_account.Credentials.from_service_account_info(creds_dict, scopes=self.SCOPES)
        except json.JSONDecodeError as e:
            raise ValueError("GOOGLE_CREDENTIALS environment variable contains invalid JSON") from e
        except ValueError as e:
            raise ValueError from e
        except Exception as e:
            raise Exception(f"Failed to initialize Google credentials: {e!s}") from e

    # no type annotation on return type, because Google doesn't give us one
    # ruff: noqa: ANN202
    def _build_sheets_service(self):
        """Create and return an authorized Sheets API service object"""
        try:
            creds = self._get_google_credentials()
            return build("sheets", "v4", credentials=creds)
        # ruff doesn't like bare exception here,
        # but I do
        # ruff: noqa: TRY002
        except Exception as e:
            logger.exception("Failed to build sheets service")
            raise SheetError(f"Could not initialize sheets service: {e!s}") from e

    def initialize_year_structure(self, sheet_name: str, year: int | None = None, *, force: bool = False) -> None:
        """Initialize the spreadsheet with all weeks and days of the year."""
        year = year or datetime.now(tz=UTC).year
        logger.info(f"Initializing year structure for {year}")

        if not force:
            current_dates = self.get_current_dates(sheet_name=sheet_name)
            date_gen = self._generate_dates(year)
            expected_dates = [date_str for _, date_str in date_gen]

            if self._validate_current_structure(current_dates, expected_dates):
                logger.info("Sheet is already properly initialized")
                return

        self._perform_initialization(sheet_name, year)

    def _generate_dates(self, year: int) -> Generator[tuple[EntryType, str], None, None]:
        """Generate sequence of dates and week headers for the year"""
        current_date = datetime(year, 1, 1, tzinfo=UTC)
        current_week = None

        while current_date.year == year:
            week_number = current_date.isocalendar()[1]

            if week_number != current_week:
                yield EntryType.WEEK_HEADER, f"Week {week_number}"
                current_week = week_number

            yield EntryType.DATE, current_date.strftime("%A, %B %-d")
            current_date += timedelta(days=1)

    @retry.Retry()
    def get_current_dates(self, sheet_name: str) -> list[str]:
        """Get the current content of column A with retry logic"""
        range_name = f"{sheet_name}!A:A"
        try:
            result = (
                self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=range_name).execute()
            )
            return [row[0] for row in result.get("values", [])[1:] if row]
        except Exception as e:
            logger.exception("Error reading current dates")
            raise SheetError(f"Failed to read current dates: {e!s}") from e

    @retry.Retry()
    def clear_sheet(self, sheet_name: str) -> None:
        """Clear all content from sheet with retry logic"""
        clear_range = f"{sheet_name}!A1:Z1000"
        try:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id, body={"ranges": [clear_range]}
            ).execute()
        except Exception as e:
            logger.exception("Error clearing sheet")
            raise SheetError(f"Failed to clear sheet: {e!s}") from e

    def _validate_current_structure(self, current: list[str], expected: list[str]) -> bool:
        """Validate if current sheet structure matches expected structure"""
        return len(current) == len(expected) and all(curr == exp for curr, exp in zip(current, expected, strict=False))

    def _perform_initialization(self, sheet_name: str, year: int) -> None:
        """Perform the actual initialization of the sheet"""
        logger.info("Starting sheet initialization")
        self.clear_sheet(sheet_name=sheet_name)
        self.update_header_row(sheet_name=sheet_name)

        batch = []
        for _entry_type, value in self._generate_dates(year):
            batch.append([value])

            if len(batch) >= self.BATCH_SIZE:
                self.append_to_sheet_formatted(sheet_name, batch)
                batch = []

        if batch:  # Don't forget remaining entries
            self.append_to_sheet_formatted(sheet_name, batch)

        logger.info("Sheet initialization completed successfully")

    @retry.Retry()
    def append_to_sheet_formatted(self, sheet_name: str, values: list[list[str]]) -> None:
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
            logger.exception("Error appending to sheet")
            raise SheetError(f"Failed to append to sheet: {e!s}") from e

    @retry.Retry()
    def get_date_row_index(self, sheet_name: str, date: date) -> int | None:
        """Find the row index for a given date"""
        date_str = date.strftime("%A, %B %-d")
        range_name = f"{sheet_name}!A:A"
        try:
            result = (
                self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=range_name).execute()
            )

            if "values" in result:
                for i, row in enumerate(result["values"]):
                    if row and row[0] == date_str:
                        return i + 1
            return None
        except Exception as e:
            logger.exception("Error finding date row")
            raise SheetError(f"Failed to find row for date {date_str}: {e!s}") from e

    @retry.Retry()
    def get_row_values(self, sheet_name: str, row_index: int) -> list[float]:
        """Get all values for a specific row"""
        range_name = f"{sheet_name}!{row_index}:{row_index}"
        try:
            result = (
                self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=range_name).execute()
            )
            return result.get("values", [[]])[0] if "values" in result else []
        except Exception as e:
            logger.exception("Error reading row values")
            raise SheetError(f"Failed to read row {row_index}: {e!s}") from e

    @retry.Retry()
    def update_row(self, sheet_name: str, row_index: int, values: list[float]) -> None:
        """Update an entire row with new values"""
        range_name = f"{sheet_name}!A{row_index}:{chr(65 + len(values))}{row_index}"
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [values]},
            ).execute()
        except Exception as e:
            logger.exception("Error updating row")
            raise SheetError(f"Failed to update row {row_index}: {e!s}") from e

    @staticmethod
    def _ensure_row_length(values: list[float], required_length: int) -> list[float]:
        """Ensure the row has the required length, padding with zeros if needed"""
        return values + [0] * (required_length + 1 - len(values))

    @retry.Retry()
    def update_header_row(self, sheet_name: str, activities: list[str] | None = None) -> None:
        """Update the header row with given activities"""
        activities = activities or []
        header_row = ["Date", *activities]
        range_name = f"{sheet_name}!A1:{chr(65 + len(header_row))}{1}"

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [header_row]},
            ).execute()
        except Exception as e:
            logger.exception("Error updating header row")
            raise SheetError(f"Failed to update header row: {e!s}") from e

    def update_activities_header(self, sheet_name: str, activity: str) -> None:
        """Add a new activity column if it doesn't exist"""
        existing_activities = self.get_activity_columns(sheet_name=sheet_name)
        if activity not in existing_activities:
            logger.info(f"Adding new activity column: {activity}")
            activities = [*existing_activities, activity]
            self.update_header_row(sheet_name=sheet_name, activities=activities)

    @retry.Retry()
    def get_activity_columns(self, sheet_name: str) -> list[str]:
        """Get list of activity names from the header row"""
        range_name = f"{sheet_name}!A1:Z1"

        try:
            result = (
                self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=range_name).execute()
            )

            if result.get("values"):
                headers = result["values"][0]
                return headers[1:] if len(headers) > 1 else []
            # ruff: noqa: TRY300
            return []

        except Exception as e:
            logger.exception("Error reading headers")
            raise SheetError(f"Failed to read activity columns: {e!s}") from e
