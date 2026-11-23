from auth import get_gmail_service

def main():
    service = get_gmail_service()
    resp = service.users().messages().list(userId="me", maxResults=10).execute()
    for m in resp.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="metadata", metadataHeaders=["Subject"]
        ).execute()
        headers = msg["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(no subject)"
        )
        print(subject)

if __name__ == "__main__":
    main()