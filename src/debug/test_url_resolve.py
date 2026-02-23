import os
import json
import socket
import sys

# Paths
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
INFRA_CONFIG = os.path.join(LAB_DIR, "config/infrastructure.json")

def resolve_brain_url():
    """Resolves the Brain's heartbeat URL from infrastructure config."""
    try:
        if os.path.exists(INFRA_CONFIG):
            with open(INFRA_CONFIG, 'r') as f:
                infra = json.load(f)
            primary = infra.get("nodes", {}).get("brain", {}).get("primary", "localhost")
            host_cfg = infra.get("hosts", {}).get(primary, {})
            ip_hint = host_cfg.get("ip_hint", "127.0.0.1")
            port = host_cfg.get("ollama_port", 11434)
            
            # Dynamic resolution
            try:
                ip = socket.gethostbyname(primary)
                print(f"[DEBUG] Resolved {primary} to {ip} via DNS")
            except Exception as e:
                ip = ip_hint
                print(f"[DEBUG] DNS resolution failed for {primary}: {e}. Using hint: {ip}")
                
            return f"http://{ip}:{port}/api/tags"
    except Exception as e:
        print(f"[DEBUG] General error: {e}")
    return "http://localhost:11434/api/tags"

if __name__ == "__main__":
    url = resolve_brain_url()
    print(f"RESULT URL: {url}")
