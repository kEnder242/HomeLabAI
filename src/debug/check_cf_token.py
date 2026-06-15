import requests
import json
import os

def check_token():
    secrets_path = "Portfolio_Dev/monitor/secrets.json"
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    cf_token = secrets.get("CF_API_TOKEN")
    headers = {"Authorization": f"Bearer {cf_token}"}
    
    res = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers=headers)
    print(json.dumps(res.json(), indent=2))

if __name__ == "__main__":
    check_token()
