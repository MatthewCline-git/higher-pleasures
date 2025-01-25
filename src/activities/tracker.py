import logging
from datetime import datetime
from typing import Optional

from ..sheets.client import GoogleSheetsClient
from .parser import OpenAIActivityParser

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Main class for tracking activities"""

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        activity_parser: OpenAIActivityParser,
        user_sheet_mapping: dict[int, str],
        year: Optional[int] = None,
    ):
        self.sheets_client = sheets_client
        self.activity_parser = activity_parser
        self.year = year or datetime.now().year
        self.user_sheet_mapping = user_sheet_mapping
        for sheet_name in set(user_sheet_mapping.values()):
            self.sheets_client.initialize_year_structure(sheet_name, self.year)

    def track_activity(self, user_id: int, message: str) -> None:
        """Track a new activity from a natural language message"""
        sheet_name = self.user_sheet_mapping.get(user_id)
        if not sheet_name:
            raise ValueError(f"No sheet mapping found for {user_id=}")
        
        existing_categories = self.sheets_client.get_activity_columns(sheet_name)
        activities = self.activity_parser.parse_message(message, existing_categories)

        date = datetime.now()
        for activity in activities:
            self.process_new_entry(
                sheet_name=sheet_name, date=date, activity=activity["activity"], duration=activity["duration"]
            )

    def process_new_entry(self, sheet_name: str, date: datetime, activity: str, duration: float) -> None:
        """Process a new activity entry with validation"""
        if duration < 0:
            raise ValueError("Duration cannot be negative")

        logger.info(
            f"Processing new entry for {sheet_name}: {activity} for {date.date()} - {duration} hours"
        )

        self.sheets_client.update_activities_header(sheet_name, activity)
        date_row_index = self.sheets_client.get_date_row_index(sheet_name, date)

        if not date_row_index:
            raise ValueError(f"Could not find row for date: {date}")

        self._update_activity_duration(sheet_name, date_row_index, activity, duration)

    def _update_activity_duration(
        self, sheet_name: str, row_index: int, activity: str, duration: float
    ) -> None:
        """Update the duration for a specific activity"""
        current_values = self.sheets_client.get_row_values(sheet_name=sheet_name, row_index=row_index)
        activities = self.sheets_client.get_activity_columns(sheet_name=sheet_name)
        activity_index = activities.index(activity) + 1

        current_values = self._ensure_row_length(current_values, activity_index)
        current_duration = float(current_values[activity_index] or 0)
        current_values[activity_index] = current_duration + duration

        self.sheets_client.update_row(sheet_name=sheet_name, row_index=row_index, values=current_values)

    @staticmethod
    def _ensure_row_length(values: list[float], required_length: int) -> list[float]:
        """Ensure the row has the required length, padding with zeros if needed"""
        return values + [0] * (required_length + 1 - len(values))
