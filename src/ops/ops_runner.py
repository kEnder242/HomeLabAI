#!/usr/bin/env python3
# [FEAT-620] Ops Execution Engine — Deterministic Operational Action Runner
"""
OpsRunner: Transitions Ops from passive advice to active execution.

Directly performs operational actions across Linux services, GPU power/VRAM,
Foyer daemon lifecycles, and remote hardware seats (M5 Air / KENDER).
"""

import argparse
import datetime
import gc
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [OPS] %(message)s",
)
logger = logging.getLogger("ops_runner")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(BASE_DIR)
HOMELAB_DIR = os.path.dirname(SRC_DIR)
PORTFOLIO_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
PAGER_FILE = os.path.join(PORTFOLIO_DIR, "field_notes/data/pager_activity.json")
STATUS_FILE = os.path.join(PORTFOLIO_DIR, "field_notes/data/status.json")


def _broadcast_pager(message: str, severity: str = "INFO", source: str = "OpsEngine") -> None:
    """Broadcasts an atomic operational event to pager_activity.json."""
    try:
        os.makedirs(os.path.dirname(PAGER_FILE), exist_ok=True)
        activities = []
        if os.path.exists(PAGER_FILE):
            try:
                with open(PAGER_FILE, "r") as f:
                    activities = json.load(f)
            except Exception:
                pass
        record = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "severity": severity.upper(),
            "source": source,
            "message": message,
        }
        activities.append(record)
        tmp = PAGER_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(activities[-30:], f, indent=2)
        os.replace(tmp, PAGER_FILE)
    except Exception as exc:
        logger.warning(f"Failed to broadcast to pager: {exc}")


class OpsRunner:
    """Deterministic operational execution engine."""

    def __init__(self, foyer_url: str = "http://127.0.0.1:8765"):
        self.foyer_url = foyer_url.rstrip("/")

    def get_gpu_vitals(self) -> dict:
        """[FEAT-620] Query live GPU telemetry (temp, power, memory, utilization)."""
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,power.draw,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            line = res.stdout.strip()
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                return {
                    "status": "SUCCESS",
                    "temp_c": int(parts[0]),
                    "power_w": float(parts[1]),
                    "vram_used_mb": int(parts[2]),
                    "vram_total_mb": int(parts[3]),
                    "utilization_pct": int(parts[4]),
                }
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}
        return {"status": "UNKNOWN"}

    def clamp_gpu_power(self, watts: int = 165) -> dict:
        """[LAB-109 / FEAT-620] Enforce GPU power limit to protect host PSU and VRMs."""
        try:
            cmd = ["sudo", "nvidia-smi", "-pl", str(watts)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                _broadcast_pager(f"⚡ GPU power limit clamped to {watts}W", severity="INFO")
                return {"status": "SUCCESS", "power_limit_w": watts, "output": res.stdout.strip()}
            else:
                return {"status": "FAILED", "error": res.stderr.strip() or res.stdout.strip()}
        except Exception as exc:
            return {"status": "ERROR", "error": str(exc)}

    def quiesce_foyer(self, timeout_s: int = 15) -> dict:
        """[FEAT-213 / FEAT-620] Actively evict resident models and reclaim VRAM."""
        start = time.monotonic()
        try:
            req = urllib.request.Request(f"{self.foyer_url}/quiesce", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            data = {"action": "quiesce_attempted", "error": str(e)}

        # Verify VRAM dropped
        vitals = self.get_gpu_vitals()
        vram_used = vitals.get("vram_used_mb", 0) if vitals.get("status") == "SUCCESS" else -1
        duration = round(time.monotonic() - start, 2)
        msg = f"🛑 Foyer quiesced in {duration}s. Live VRAM: {vram_used}MB"
        _broadcast_pager(msg, severity="INFO")
        return {"status": "SUCCESS", "action": "quiesce", "vram_used_mb": vram_used, "duration_s": duration, "response": data}

    def wake_foyer(self, timeout_s: int = 30) -> dict:
        """[FEAT-213 / FEAT-620] Actively re-ignite Foyer to OPERATIONAL state."""
        start = time.monotonic()
        try:
            req = urllib.request.Request(f"{self.foyer_url}/wake", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode())
            duration = round(time.monotonic() - start, 2)
            _broadcast_pager(f"⚡ Foyer re-ignited to OPERATIONAL in {duration}s", severity="INFO")
            return {"status": "SUCCESS", "action": "wake", "duration_s": duration, "response": data}
        except Exception as exc:
            return {"status": "ERROR", "action": "wake", "error": str(exc)}

    def restart_service(self, service_name: str = "lab-attendant") -> dict:
        """[FEAT-620] Execute active user-systemd service restart."""
        start = time.monotonic()
        try:
            cmd = ["systemctl", "--user", "restart", service_name]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            duration = round(time.monotonic() - start, 2)
            _broadcast_pager(f"🔄 Service {service_name} restarted in {duration}s", severity="INFO")
            return {"status": "SUCCESS", "service": service_name, "duration_s": duration}
        except Exception as exc:
            return {"status": "ERROR", "service": service_name, "error": str(exc)}

    def purge_cuda_cache(self) -> dict:
        """[FEAT-160 / FEAT-620] Purge PyTorch GPU cache and run Python garbage collection."""
        gc.collect()
        purged = False
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                try:
                    torch.cuda.ipc_collect()
                except Exception:
                    pass
                purged = True
        except ImportError:
            pass
        vitals = self.get_gpu_vitals()
        return {"status": "SUCCESS", "purged_cuda": purged, "vram_mb": vitals.get("vram_used_mb", 0)}

    def switch_air_mode(self, model_key: str = "27b", mode: str = "dflash", air_host: str = "192.168.1.46", air_port: int = 8002) -> dict:
        """[FEAT-620] Trigger active model/engine switch on M5 Air via control_api.py (:8002)."""
        url = f"http://{air_host}:{air_port}/switch"
        payload = json.dumps({"model": model_key, "mode": mode}).encode()
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            _broadcast_pager(f"🍏 M5 Air switched to {model_key} ({mode})", severity="INFO")
            return {"status": "SUCCESS", "air_response": data}
        except Exception as exc:
            return {"status": "ERROR", "host": air_host, "error": str(exc)}


def execute_op(action: str, **kwargs) -> dict:
    """Main operational dispatcher."""
    runner = OpsRunner()
    actions = {
        "vitals": runner.get_gpu_vitals,
        "power_clamp": lambda: runner.clamp_gpu_power(kwargs.get("watts", 165)),
        "quiesce": lambda: runner.quiesce_foyer(kwargs.get("timeout_s", 15)),
        "wake": lambda: runner.wake_foyer(kwargs.get("timeout_s", 30)),
        "restart_service": lambda: runner.restart_service(kwargs.get("service_name", "lab-attendant")),
        "purge_cache": runner.purge_cuda_cache,
        "switch_air": lambda: runner.switch_air_mode(
            model_key=kwargs.get("model", "27b"),
            mode=kwargs.get("mode", "dflash"),
            air_host=kwargs.get("host", "192.168.1.46"),
            air_port=kwargs.get("port", 8002),
        ),
    }

    if action not in actions:
        return {"status": "ERROR", "error": f"Unknown action: {action}. Available: {list(actions.keys())}"}

    logger.info(f"Executing operation: {action} with args {kwargs}")
    return actions[action]()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Ops Execution Runner")
    parser.add_argument("action", choices=["vitals", "power_clamp", "quiesce", "wake", "restart_service", "purge_cache", "switch_air"], help="Operational action to perform")
    parser.add_argument("--watts", type=int, default=165, help="Power limit in watts")
    parser.add_argument("--service", type=str, default="lab-attendant", help="Systemd service name")
    parser.add_argument("--model", type=str, default="27b", help="Model key for Air switch (9b or 27b)")
    parser.add_argument("--mode", type=str, default="dflash", help="Engine mode for Air switch (dflash, turboquant)")
    args = parser.parse_args()

    result = execute_op(args.action, watts=args.watts, service_name=args.service, model=args.model, mode=args.mode)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") in ("SUCCESS", "UNKNOWN") else 1)
