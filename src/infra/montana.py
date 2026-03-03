import logging
import os
import sys
import uuid
import subprocess

# Global Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_LOG = os.path.join(LAB_DIR, "server.log")

_logger_initialized = False
_BOOT_HASH = uuid.uuid4().hex[:4].upper()

def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], 
                                        cwd=LAB_DIR, text=True).strip()
    except Exception:
        return "unknown"

_SOURCE_COMMIT = get_git_commit()

def get_fingerprint(role="NODE"):
    return f"[{_BOOT_HASH}:{_SOURCE_COMMIT}:{role}]"

def reclaim_logger(role="NODE"):
    """
    [BKM-002] The Montana Protocol: Reclaims log visibility from third-party hijackers.
    Forces all logs to sys.stderr and the central server.log.
    """
    global _logger_initialized
    if _logger_initialized:
        # If already initialized, we don't clear handlers again, 
        # but we might update the role if it was generic.
        return

    root = logging.getLogger()
    # Aggressively clear all existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    fmt = logging.Formatter(
        f"%(asctime)s - {get_fingerprint(role)} %(levelname)s - %(message)s"
    )

    # Console Handler (Stderr)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # File Handler
    fh = logging.FileHandler(SERVER_LOG, mode="a", delay=False)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Set Levels
    root.setLevel(logging.INFO)
    
    # Mute noisy internal loggers
    logging.getLogger("nemo").setLevel(logging.ERROR)
    logging.getLogger("chromadb").setLevel(logging.ERROR)
    logging.getLogger("onelogger").setLevel(logging.ERROR)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    _logger_initialized = True
    logging.info(f"[MONTANA] Log visibility reclaimed for {role}.")
