import logging
from datetime import UTC, date, datetime

from src.activities.parser import OpenAIActivityParser
from src.db.client import SQLiteClient
from src.sheets.client import GoogleSheetsClient


logger = logging.getLogger(__name__)


class ActivityTracker:
    """Main class for tracking activities"""

    def __init__(
        self,
        sheets_client: GoogleSheetsClient,
        activity_parser: OpenAIActivityParser,
        user_sheet_mapping: dict[int, str],
        year: int | None = None,
        db_client: SQLiteClient | None = None,
    ) -> None:
        self.sheets_client = sheets_client
        self.activity_parser = activity_parser
        self.year = year or datetime.now(tz=UTC).year
        self.db_client = db_client
        self.user_sheet_mapping = user_sheet_mapping
        for sheet_name in set(user_sheet_mapping.values()):
            self.sheets_client.initialize_year_structure(sheet_name, self.year)

    def track_activity(self, telegram_user_id: int, message: str, db_user_id: int | None = None) -> None:
        """Track a new activity from a natural language message"""
        sheet_name = self.user_sheet_mapping.get(telegram_user_id)
        if not sheet_name:
            raise ValueError(f"No sheet mapping found for {telegram_user_id=}")

        existing_categories = self.sheets_client.get_activity_columns(sheet_name)

        if self.db_client is not None:
            db_user_id = self.db_client.get_user_id_from_telegram(telegram_user_id)
            existing_categories = self.db_client.get_user_activities(user_id=db_user_id)

        activities = self.activity_parser.parse_message(message, existing_categories)

        for activity in activities:
            self.process_new_entry_sheets(
                sheet_name=sheet_name,
                date=activity["date"],
                activity=activity["activity"],
                duration=activity["duration"],
            )
            if self.db_client is not None:
                self.process_new_entry(
                    db_user_id=db_user_id,
                    activity=activity["activity"],
                    date=activity["date"],
                    duration_minutes=int(round(activity["duration"] * 60)),
                    raw_input=message,
                )

    def process_new_entry(
        self,
        db_user_id: int,
        activity: str,
        date: date,
        duration_minutes: int,
        raw_input: str,
    ) -> None:
        """Process a new activity entry"""
        if self.db_client is None:
            return

        user_activity_id = self.db_client.get_user_activity_id_from_activity(user_id=db_user_id, activity=activity)
        if user_activity_id is None:
            user_activity_id = self.db_client.insert_activity(db_user_id, activity)
        self.db_client.insert_entry(db_user_id, user_activity_id, date, duration_minutes, raw_input)

    def process_new_entry_sheets(self, sheet_name: str, date: date, activity: str, duration: float) -> None:
        """Process a new activity entry with validation"""
        if duration < 0:
            raise ValueError("Duration cannot be negative")

        logger.info(f"Processing new entry for {sheet_name}: {activity} for {date} - {duration} hours")

        self.sheets_client.update_activities_header(sheet_name, activity)
        date_row_index = self.sheets_client.get_date_row_index(sheet_name, date)

        if not date_row_index:
            raise ValueError(f"Could not find row for date: {date}")

        self._update_activity_duration(sheet_name, date_row_index, activity, duration)

    def _update_activity_duration(self, sheet_name: str, row_index: int, activity: str, duration: float) -> None:
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
