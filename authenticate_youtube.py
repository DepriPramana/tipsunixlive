import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Settings
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]
CREDENTIALS_FILE = 'client_secrets.json'
TOKEN_FILE = 'youtube_token.pickle'

def authenticate():
    creds = None
    
    # 1. Try to load existing token
    if os.path.exists(TOKEN_FILE):
        print(f"Loading existing token from {TOKEN_FILE}...")
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Error loading token: {e}")
    
    # 2. Refresh or Create
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Refresh failed: {e}")
                creds = None
        
        if not creds:
            print("Starting new authentication flow...")
            # Handle potential filename mismatch
            creds_file = CREDENTIALS_FILE
            if not os.path.exists(creds_file) and os.path.exists('client_secret.json'):
                creds_file = 'client_secret.json'
                
            if not os.path.exists(creds_file):
                print(f"ERROR: Credentials file not found ({CREDENTIALS_FILE} or client_secret.json)")
                return
            
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_file, SCOPES
            )
            
            # This will allow copy-pasting the URL if browser checks fail,
            # or simply run local server without opening browser.
            # Using run_console is often better for remote SSH sessions as it 
            # uses the copy-paste flow which doesn't require port forwarding.
            print("\nPlease choose authentication method:")
            print("1. Local Server (requires port 8080 forwarding)")
            print("2. Console/Manual (copy-paste code)")
            
            choice = input("Enter choice (1/2): ").strip()
            
            if choice == '2':
                creds = flow.run_console()
            else:
                print("\nPlease visit the URL below to authenticate. Ensure port 8080 is forwarded.")
                creds = flow.run_local_server(port=8080, open_browser=False)
        
        # Save
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print(f"\nSUCCESS: Token saved to {TOKEN_FILE}")
    else:
        print("Token is already valid!")

if __name__ == '__main__':
    authenticate()
