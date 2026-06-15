import requests
import json
import os

def final_attempt():
    secrets_path = "Portfolio_Dev/monitor/secrets.json"
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    cf_token = secrets.get("CF_API_TOKEN")
    cf_account = secrets.get("CF_ACCOUNT_ID")
    app_id = "8a77121a-5cd3-4f3e-aaf0-4df2cd07cfe1"

    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }

    # Use PUT with FULL payload to avoid Method Not Allowed
    # Some Cloudflare endpoints only support PUT for full updates
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/access/apps/{app_id}"
    
    data = {
        "name": "Jason Lab - Sovereign",
        "domain": "notes.jason-lab.dev",
        "type": "self_hosted",
        "session_duration": "24h",
        "options_preflight_bypass": False,
        "cors_headers": {
            "allow_all_headers": False,
            "allow_all_methods": False,
            "allow_all_origins": False,
            "allow_credentials": True,
            "allowed_headers": ["Content-Type", "X-Lab-Key", "Authorization"],
            "allowed_methods": ["GET", "POST", "OPTIONS"],
            "allowed_origins": [
                "https://notes.jason-lab.dev", 
                "https://www.jason-lab.dev", 
                "https://code.jason-lab.dev",
                "https://pager.jason-lab.dev",
                "http://localhost:9001"
            ],
            "max_age": 3600
        }
    }

    print(f"PUTing {url}...")
    res = requests.put(url, headers=headers, json=data)
    
    if res.status_code == 200:
        print("✅ SUCCESS: Cloudflare Access configured.")
    else:
        print(f"❌ FAILED: {res.status_code} - {res.text}")

if __name__ == "__main__":
    final_attempt()
