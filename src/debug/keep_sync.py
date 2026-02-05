import gkeepapi
import json
import os
import re

# Credentials from user
EMAILS = ['kEnder242@gmail.com', 'kender242@gmail.com']
PASSWORD = 'azdrrjkntjyakvkv'
PASSWORD_SPACES = 'azdr rjkn tjya kvkv'
AUTH_FILE = os.path.expanduser('~/.config/gkeep/auth.json')

def login():
    keep = gkeepapi.Keep()
    
    # Try to load existing token
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r') as f:
                auth_data = json.load(f)
                if 'token' in auth_data:
                    keep.resume(auth_data.get('username', EMAILS[0]), auth_data['token'])
                    print("Logged in using cached token.")
                    return keep
        except Exception as e:
            print(f"Failed to resume session: {e}")

    # Fallback to App Password login
    for email in EMAILS:
        for pwd in [PASSWORD, PASSWORD_SPACES]:
            print(f"Attempting login for {email}...")
            try:
                keep.login(email, pwd)
                # Save token for next time
                os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
                with open(AUTH_FILE, 'w') as f:
                    json.dump({
                        'token': keep.getMasterToken(),
                        'username': email
                    }, f)
                print(f"Login successful for {email}. Token cached.")
                return keep
            except Exception as e:
                print(f"Login failed for {email} with pwd {pwd[:4]}...: {e}")
    
    return None

def extract_urls(text):
    return re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)

def main():
    keep = login()
    if not keep:
        print("\n!!! ACTION REQUIRED !!!")
        print("I cannot authenticate with the provided App Password.")
        print("This is often due to Google security policies (New Device/IP).")
        print("Please verify the App Password is still active at:")
        print("https://myaccount.google.com/apppasswords")
        return

    keep.sync()
    label_ai = keep.findLabel('AI')
    if not label_ai:
        print("Label 'AI' not found.")
        # List all labels to help debug
        print("Available labels:", [l.name for l in keep.labels()])
        return

    notes = keep.find(archived=False, labels=[label_ai])
    
    extracted_data = []
    
    print("\n--- Processing AI Notes ---")
    for n in notes:
        urls = extract_urls(n.text)
        if urls:
            print(f"Found {len(urls)} URLs in: {n.title or 'Untitled Note'}")
            extracted_data.append({
                'title': n.title,
                'text': n.text,
                'urls': urls,
                'id': n.id
            })
        else:
            print(f"Skipping note (no URLs): {n.title or 'Untitled Note'}")

    with open('HomeLabAI/docs/KEEP_SYNC_STATE.json', 'w') as f:
        json.dump(extracted_data, f, indent=2)
    
    print(f"\nExtracted {len(extracted_data)} notes with URLs to HomeLabAI/docs/KEEP_SYNC_STATE.json")

if __name__ == "__main__":
    main()
