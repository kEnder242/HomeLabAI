import pytest
import subprocess
import os
import requests
from typing import Optional

def _find_repo_root(start_dir: str) -> str:
    """Walk up from start_dir until a directory containing a .git entry is found."""
    current = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start_dir)
        current = parent

REPO_ROOT = _find_repo_root(os.path.dirname(__file__))

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Pytest session start hook to verify boot commit consistency.

    Computes local git commit and fetches served commit from lab-attendant.
    Prints warnings if mismatch or unreachable, OK if match.
    """
    # Compute local boot commit
    local_commit: Optional[str] = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            local_commit = result.stdout.strip()
    except Exception:
        local_commit = None

    # Try to fetch served boot commit from local lab-attendant service
    served_commit: Optional[str] = None
    try:
        response = requests.get("http://127.0.0.1:8765/version", timeout=2)
        if response.status_code == 200:
            data = response.json()
            served_commit = data.get("boot_commit")
    except Exception:
        served_commit = None

    # Generate appropriate output
    if local_commit and served_commit:
        if local_commit == served_commit:
            print(f"✅ boot commit OK: {local_commit}")
        else:
            _print_warning_box(
                f"[WARN] STALE BYTECODE\nLocal:  {local_commit}\nServed: {served_commit}"
            )
    elif local_commit:
        _print_warning_box(
            f"[WARN] SERVER UNREACHABLE\nLocal:  {local_commit}\nServed: unknown"
        )
    elif served_commit:
        _print_warning_box(
            f"[WARN] GIT UNAVAILABLE\nLocal:  unknown\nServed: {served_commit}"
        )
    else:
        print("[WARN] Could not determine boot commit (git/service unavailable)")

def _print_warning_box(message: str):
    """Print ASCII box with warning message."""
    lines = message.split('\n')
    max_len = max(len(line) for line in lines)
    border = "=" * (max_len + 4)
    print(border)
    for line in lines:
        print(f"| {line.ljust(max_len)} |")
    print(border)
