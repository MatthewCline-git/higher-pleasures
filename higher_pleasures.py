from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account


class ActivityTracker:
    def __init__(self, credentials_path, spreadsheet_id, sheet_name):
        self.SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_path = credentials_path
        self.service = self.build_sheets_service()

    def build_sheets_service(self):
        """Create an return an authorized Sheets API service object"""
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )
        return build("sheets", "v4", credentials=creds)

    def get_activity_columns(self):
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
            else:
                return []

        except Exception as e:
            print(f"Error reading headers: {e}")
            return []

    def add_new_activity(self, existing_activities, new_activity):
        """Add new activity to the list if it doesn't exist"""
        if new_activity not in existing_activities:
            return existing_activities + [new_activity]
        return existing_activities

    def update_header_row(self, activities):
        """Update the header row with all activities"""
        header_row = ["Date"] + activities

        body = {"values": [header_row]}

        range_name = f"{self.sheet_name}!A1:{chr(65 + len(header_row))}{1}"

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
        except Exception as e:
            print(f"Error updating header row: {e}")
            raise

    def get_last_entry_date(self):
        """Get the date from the last row in the sheet"""
        range_name = f"{self.sheet_name}!A:A"
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )

        if "values" in result and len(result["values"]) > 1:  # Skip header
            last_date_str = result["values"][-1][0]
            return datetime.strptime(last_date_str, "%A, %B %d %Y")
        return None

    def handle_missing_days(self, last_date, current_date, activities):
        """Fill in missing days with zeros"""
        if not last_date:
            return

        day_after_last = last_date + timedelta(days=1)
        while day_after_last.date() < current_date.date():
            missing_row = self.create_row_data(day_after_last, None, 0, activities)
            self.append_to_sheet([missing_row])
            day_after_last += timedelta(days=1)

    def is_new_week(self, last_date, current_date):
        """
        Determine if we need a new week header
        Returns (bool, date) where date is the Sunday that started the new week
        """
        if not last_date:
            # First entry ever - start a new week
            days_since_sunday = current_date.weekday() + 1
            sunday = current_date - timedelta(days=days_since_sunday)
            return True, sunday

        days_since_sunday = current_date.weekday() + 1
        current_week_sunday = current_date - timedelta(days=days_since_sunday)
        last_days_since_sunday = (last_date.weekday() + 1) % 7
        last_week_sunday = last_date - timedelta(days=last_days_since_sunday)
        return (
            current_week_sunday.date() != last_week_sunday.date()
        ), current_week_sunday

    def get_date_row_index(self, date):
        """Find the index of today's row if it exists"""
        date_str = date.strftime("%A, %B %d %Y")
        range_name = f"{self.sheet_name}!A:A"  # Get all dates

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )

            if "values" in result:
                # Look for today's date in the first column
                for i, row in enumerate(result["values"]):
                    if row and row[0] == date_str:
                        return i + 1  # Add 1 because sheets are 1-indexed
            return None

        except Exception as e:
            print(f"Error finding today's row: {e}")
            return None

    def get_row_values(self, row_index):
        """Get all values in a specific row"""
        range_name = f"{self.sheet_name}!{row_index}:{row_index}"
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [[]])[0] if "values" in result else []

    def update_row(self, row_index, values):
        """Update an existing row with new values"""
        range_name = (
            f"{self.sheet_name}!A{row_index}:{chr(65 + len(values))}{row_index}"
        )
        body = {"values": [values]}
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

    def create_row_data(self, date, activity, duration, activity_columns):
        """Create a row with the correct activity in the correct column"""
        row = [date.strftime("%A, %B %d %Y")]
        for col in activity_columns:
            if activity == col:
                row.append(duration)
            else:
                row.append(0)

        return row

    def append_to_sheet(self, values):
        """Append rows to the sheet"""
        body = {"values": values}

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

        print(f"Appended to range: {result.get('updates').get('updatedRange')}")

    def add_week_header(self, week_number, activities):
        """Add a week header row"""
        header = [f"Week {week_number}"] + [""] * len(activities)
        print(f"{header=}")
        self.append_to_sheet([header])

    def handle_activities_header(self, activity, activities):
        if activity not in activities:
            activities = self.add_new_activity(activities, activity)
            self.update_header_row(activities)

    def process_new_entry(self, date, activity, duration):
        """Main function to process a new time entry"""
        activities = self.get_activity_columns()
        self.handle_activities_header(activity, activities)

        last_date = self.get_last_entry_date()
        # Handle any missing days before this entry
        self.handle_missing_days(last_date, date, activities)

        # Check if we need a new week header
        needs_new_week, sunday = self.is_new_week(last_date, date)
        print(f"{needs_new_week=}")
        if needs_new_week:
            week_number = sunday.isocalendar()[1]
            print(f"{week_number=}")
            self.add_week_header(week_number, activities)

        date_row_index = self.get_date_row_index(date)
        if date_row_index:
            current_values = self.get_row_values(date_row_index)
            print(f"{current_values=}")
            activity_index = activities.index(activity) + 1

            if len(current_values) > activity_index:
                current_duration = float(current_values[activity_index] or 0)
                current_values[activity_index] = current_duration + duration
            else:
                # Extend the row if needed
                while len(current_values) <= activity_index:
                    current_values.append(0)
                current_values[activity_index] = duration

            # Update the row
            self.update_row(date_row_index, current_values)
        else:
            # Create new row if no entry exists for today
            row_data = self.create_row_data(date, activity, duration, activities)
            self.append_to_sheet([row_data])


if __name__ == "__main__":
    SPREADSHEET_ID = "1-Diy__NG89KaYEFdPdpTP3msn0Sl63TX_vqPX2nAu44"
    SHEET_NAME = "Sheet2"
    CREDENTIALS_PATH = "./secrets/higher_pleasures_keys.json"

    tracker = ActivityTracker(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)

    tracker.process_new_entry(
        date=datetime.now() + timedelta(days=3), activity="Swimming", duration=1.5
    )
