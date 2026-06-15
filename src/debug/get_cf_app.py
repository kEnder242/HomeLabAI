import requests
import json
import os

def get_app_details():
    secrets_path = "Portfolio_Dev/monitor/secrets.json"
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    cf_token = secrets.get("CF_API_TOKEN")
    zone_id = "c560564464f6202dde62e8e67649f79c"
    app_id = "8a77121a-5cd3-4f3e-aaf0-4df2cd07cfe1"

    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }

    res = requests.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/access/apps/{app_id}", headers=headers)
    print(json.dumps(res.json().get("result"), indent=2))

if __name__ == "__main__":
    get_app_details()
