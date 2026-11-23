"""Google OAuth with token persistence and automatic re-consent."""
import os
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

TOKEN = "token.json"
CLIENT_SECRETS = "credentials.json"


def _consent():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    return flow.run_local_server(port=0)


def get_credentials():
    creds = None

    if os.path.exists(TOKEN):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
        except ValueError:
            creds = None  # token file is for a different scope set

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Testing-mode refresh tokens expire after 7 days. Start over.
            print("Saved token is no longer valid - re-authenticating.")
            os.remove(TOKEN)
            creds = None

    if not creds or not creds.valid:
        creds = _consent()

    with open(TOKEN, "w") as f:
        f.write(creds.to_json())

    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())


def get_calendar_service():
    return build("calendar", "v3", credentials=get_credentials())
