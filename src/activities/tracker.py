import logging
from datetime import datetime
from typing import Optional

from ..sheets.client import GoogleSheetsClient
from .parser import ActivityParser

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Main class for tracking activities"""

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        activity_parser: ActivityParser,
        year: Optional[int] = None,
    ):
        self.sheets_client = sheets_client
        self.activity_parser = activity_parser
        self.year = year or datetime.now().year

    def track_activity(self, message: str, date: Optional[datetime] = None) -> None:
        """Track a new activity from a natural language message"""
        existing_categories = self.sheets_client.get_activity_columns()
        parsed = self.activity_parser.parse_message(message, existing_categories)

        date = date or datetime.now()
        self.process_new_entry(
            date=date, activity=parsed["activity"], duration=parsed["duration"]
        )

    def process_new_entry(self, date: datetime, activity: str, duration: float) -> None:
        """Process a new activity entry with validation"""
        if duration < 0:
            raise ValueError("Duration cannot be negative")

        logger.info(
            f"Processing new entry: {activity} for {date.date()} - {duration} hours"
        )

        self.sheets_client.update_activities_header(activity)
        date_row_index = self.sheets_client.get_date_row_index(date)

        if not date_row_index:
            raise ValueError(f"Could not find row for date: {date}")

        self._update_activity_duration(date_row_index, activity, duration)

    def _update_activity_duration(
        self, row_index: int, activity: str, duration: float
    ) -> None:
        """Update the duration for a specific activity"""
        current_values = self.sheets_client.get_row_values(row_index)
        activities = self.sheets_client.get_activity_columns()
        activity_index = activities.index(activity) + 1

        current_values = self._ensure_row_length(current_values, activity_index)
        current_duration = float(current_values[activity_index] or 0)
        current_values[activity_index] = current_duration + duration

        self.sheets_client.update_row(row_index, current_values)

    @staticmethod
    def _ensure_row_length(values: list[float], required_length: int) -> list[float]:
        """Ensure the row has the required length, padding with zeros if needed"""
        return values + [0] * (required_length + 1 - len(values))
