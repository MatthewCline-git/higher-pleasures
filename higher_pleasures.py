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

    def get_expected_dates(self, year):
        """Generate the expected sequence of dates and week headers"""
        expected = []
        rows_batch = []  # Store the actual rows we'll need for initialization
        current_date = datetime(year, 1, 1)
        current_week = None
        
        while current_date.year == year:
            week_number = current_date.isocalendar()[1]
            
            if week_number != current_week:
                week_header = f"Week {week_number}"
                expected.append(week_header)
                rows_batch.append([week_header])
                current_week = week_number
            
            date_str = f"{current_date.strftime('%A, %B %-d')}"
            expected.append(date_str)
            rows_batch.append([date_str])
            current_date += timedelta(days=1)
            
        return expected, rows_batch
    
    def get_current_dates(self):
        """Get the current content of column A"""
        range_name = f"{self.sheet_name}!A:A"
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
            
            if "values" in result:
                # Flatten the 2D array and skip the header row
                return [row[0] for row in result["values"][1:] if row]
            return []
            
        except Exception as e:
            print(f"Error reading current dates: {e}")
            return []
        
    def clear_sheet(self):
        """Clear all content from sheet"""
        clear_range = f"{self.sheet_name}!A1:Z1000"
        body = {
            "ranges": [clear_range]
        }
        try:
            self.service.spreadsheets().values().batchClear(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
        except Exception as e:
            print(f"Error clearing sheet: {e}")
            raise

    def initialize_year_structure(self, year=None, force=False):
        """Initialize the spreadsheet with all weeks and days of the year."""
        if year is None:
            year = datetime.now().year
        
        expected_dates, rows_to_write = self.get_expected_dates(year)

        if not force:
            current_dates = self.get_current_dates()
            if len(current_dates) == len(expected_dates):
                if all(current == expected for current, expected in zip(current_dates, expected_dates)):
                    print("Sheet is already properly initialized.")
                    return
                else:
                    print("Content mismatch found.")
            else:
                print(f"Length mismatch: current={len(current_dates)}, expected={len(expected_dates)}")

        print("Initializing sheet...")
        
        # Clear and initialize
        self.clear_sheet()
        self.update_header_row()
        
        # Write rows in batches of 50
        for i in range(0, len(rows_to_write), 50):
            batch = rows_to_write[i:i + 50]
            self.append_to_sheet_formatted(batch)
            
        print("Initialization complete.")

    def append_to_sheet_formatted(self, values):
        """Append rows to the sheet with explicit text formatting"""
        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={'values': values}
            )
            .execute()
        )

    def update_header_row(self, activities=None):
        """Update the header row with all activities"""
        if activities is None:
            activities = []

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
        
    def update_activities_header(self, activity):
        existing_activities = self.get_activity_columns()
        if activity not in existing_activities:
            activities = existing_activities + [activity]
            self.update_header_row(activities)

    def get_date_row_index(self, date):
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
            print(f"Error finding today's row: {e}")
            return None
    
    def get_row_values(self, row_index):
        range_name = f"{self.sheet_name}!{row_index}:{row_index}"
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [[]])[0] if "values" in result else []
    
    def update_row(self, row_index, values):
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

    def process_new_entry(self, date, activity, duration):
        # first add a column for the new activity if needed
        self.update_activities_header(activity)
        date_row_index = self.get_date_row_index(date)
        current_values = self.get_row_values(date_row_index)
        activities = self.get_activity_columns()
        activity_index = activities.index(activity) + 1 # sheets are 1-indexed

        if len(current_values) > activity_index:
            current_duration = float(current_values[activity_index] or 0)
            current_values[activity_index] = current_duration + duration

        else:
            while len(current_values) <= activity_index:
                current_values.append(0)
            current_values[activity_index] = duration
        self.update_row(date_row_index, current_values)

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

if __name__ == "__main__":
    SPREADSHEET_ID = "1-Diy__NG89KaYEFdPdpTP3msn0Sl63TX_vqPX2nAu44"
    SHEET_NAME = "Sheet2"
    CREDENTIALS_PATH = "./secrets/higher_pleasures_keys.json"

    tracker = ActivityTracker(CREDENTIALS_PATH, SPREADSHEET_ID, SHEET_NAME)
    tracker.initialize_year_structure()
    tracker.process_new_entry(
        date=datetime.now() + timedelta(days=2), activity="Reading", duration=1.5
    )
