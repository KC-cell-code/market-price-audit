import gspread
from google.oauth2.service_account import Credentials

# Define Google Sheets API scope
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

try:
    # 1. Authenticate using the downloaded credentials JSON
    creds = Credentials.from_service_account_file(
        "google_credentials.json", scopes=SCOPES
    )
    client = gspread.authorize(creds)

    # 2. Open the spreadsheet and select the first sheet
    sheet = client.open("Audit_Subscribers").sheet1

    # 3. Append a test row to verify write permissions
    test_email = "test_connection@example.com"
    sheet.append_row([test_email])

    # 4. Fetch all rows in Column A to verify read access
    emails = sheet.col_values(1)

    print("✅ SUCCESS: Connected to Google Sheets!")
    print(f"Current entries in Column A: {emails}")

except FileNotFoundError:
    print("❌ ERROR: 'google_credentials.json' was not found in your project folder.")
except gspread.exceptions.SpreadsheetNotFound:
    print("❌ ERROR: Spreadsheet named 'Audit_Subscribers' not found. Check the title or share permissions.")
except Exception as e:
    print(f"❌ ERROR: Connection failed - {e}")