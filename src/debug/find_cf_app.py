import requests
import json
import os

def find_by_aud():
    secrets_path = "Portfolio_Dev/monitor/secrets.json"
    with open(secrets_path, 'r') as f:
        secrets = json.load(f)

    cf_token = secrets.get("CF_API_TOKEN")
    cf_account = secrets.get("CF_ACCOUNT_ID")
    target_aud = "b80095ed6d53c591ec2cf509795a25c16abebdbf2dd102154de1449b4fe80779"

    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json"
    }

    # 1. Search Account Apps
    res = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/access/apps", headers=headers)
    for app in res.json().get("result", []):
        if app.get("aud") == target_aud:
            print(f"MATCH FOUND: {app['name']} ({app['domain']}) ID: {app['id']}")

    # 2. Search Zone Apps
    z_res = requests.get("https://api.cloudflare.com/client/v4/zones", headers=headers)
    for zone in z_res.json().get("result", []):
        z_id = zone["id"]
        za_res = requests.get(f"https://api.cloudflare.com/client/v4/zones/{z_id}/access/apps", headers=headers)
        for app in za_res.json().get("result", []):
            if app.get("aud") == target_aud:
                print(f"MATCH FOUND in Zone {zone['name']}: {app['name']} ({app['domain']}) ID: {app['id']}")

if __name__ == "__main__":
    find_by_aud()
