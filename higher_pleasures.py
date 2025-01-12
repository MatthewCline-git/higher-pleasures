from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADHSHEET_ID = "1-Diy__NG89KaYEFdPdpTP3msn0Sl63TX_vqPX2nAu44"
SHEET_NAME = "Sheet2"


def append_to_sheet(values):
    creds = service_account.Credentials.from_service_account_file(
        "./secrets/higher_pleasures_keys.json", scopes=SCOPES
    )

    service = build("sheets", "v4", credentials=creds)
    body = {"values": values}

    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=SPREADHSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )

    print(f"Appended to range: {result.get('updates').get('updatedRange')}")


test_row = [["2024-01-11 14:30:00", "Piano Practice", "90 minutes"]]

append_to_sheet(test_row)
