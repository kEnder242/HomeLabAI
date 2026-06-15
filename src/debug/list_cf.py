import requests
import json
import os

def list_all_everywhere():
    secrets_path = "Portfolio_Dev/monitor/secrets.json"
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    cf_token = secrets.get("CF_API_TOKEN")
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }

    # 1. List Accounts
    accs_res = requests.get("https://api.cloudflare.com/client/v4/accounts", headers=headers)
    accounts = accs_res.json().get("result", [])
    for acc in accounts:
        acc_id = acc["id"]
        print(f"ACCOUNT: {acc['name']} ({acc_id})")
        
        # List Apps for this account
        apps_res = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{acc_id}/access/apps?per_page=100", headers=headers)
        if apps_res.status_code == 200:
            for app in apps_res.json().get("result", []):
                print(f"  - APP: {app['name']} | {app['domain']} | {app['id']}")
        
    # 2. List Zones
    zones_res = requests.get("https://api.cloudflare.com/client/v4/zones", headers=headers)
    for zone in zones_res.json().get("result", []):
        z_id = zone["id"]
        print(f"ZONE: {zone['name']} ({z_id})")
        za_res = requests.get(f"https://api.cloudflare.com/client/v4/zones/{z_id}/access/apps?per_page=100", headers=headers)
        if za_res.status_code == 200:
            for app in za_res.json().get("result", []):
                print(f"  - ZONE_APP: {app['name']} | {app['domain']} | {app['id']}")

if __name__ == "__main__":
    list_all_everywhere()
