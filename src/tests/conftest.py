import pytest
import subprocess
import os
import sys
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

def get_bytecode_status(repo_root: Optional[str] = None) -> tuple[Optional[str], Optional[str], Optional[bool]]:
    """[FEAT-524] Core evaluator for local Git HEAD vs served Lab Attendant boot commit."""
    root = repo_root or REPO_ROOT
    local_commit: Optional[str] = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            local_commit = result.stdout.strip()
    except Exception:
        local_commit = None

    served_commit: Optional[str] = None
    is_vocal_status: Optional[bool] = None
    try:
        response = requests.get("http://127.0.0.1:8765/status?timeout=60", timeout=60)
        if response.status_code == 200:
            data = response.json()
            served_commit = data.get("boot_commit")
            is_vocal_status = data.get("vocal", False)
        else:
            ver_resp = requests.get("http://127.0.0.1:8765/version", timeout=2)
            if ver_resp.status_code == 200:
                served_commit = ver_resp.json().get("boot_commit")
    except Exception:
        served_commit = None

    return local_commit, served_commit, is_vocal_status


def assert_live_bytecode(repo_root: Optional[str] = None, enforce_vocal: bool = False):
    """[FEAT-524] Standalone / Pytest callable gate enforcing fresh bytecode before live runs."""
    local_commit, served_commit, is_vocal_status = get_bytecode_status(repo_root)

    if not served_commit:
        err = (
            "LIVE INTEGRITY VIOLATION: Lab attendant is unreachable on port 8765.\n"
            "Live certification requires an active, running lab attendant service."
        )
        if "pytest" in sys.modules:
            pytest.fail(err)
        else:
            _print_warning_box(f"[ERROR] SERVER UNREACHABLE\nLocal: {local_commit}\nServed: unknown")
            raise RuntimeError(err)

    if local_commit and served_commit != local_commit:
        err = (
            f"LIVE INTEGRITY VIOLATION: Stale bytecode detected on port 8765!\n"
            f"Local Git Commit:   {local_commit}\n"
            f"Served Boot Commit: {served_commit}\n"
            f"The live server must match current git HEAD before live certification.\n"
            f"Action required: 'sudo systemctl restart lab-attendant.service'"
        )
        if "pytest" in sys.modules:
            pytest.fail(err)
        else:
            _print_warning_box(
                f"[ERROR] STALE BYTECODE\nLocal:  {local_commit}\nServed: {served_commit}"
            )
            raise RuntimeError(err)

    if enforce_vocal and not is_vocal_status:
        err = "LIVE INTEGRITY VIOLATION: Lab is not in a vocal state (vocal=False)."
        if "pytest" in sys.modules:
            pytest.fail(err)
        else:
            _print_warning_box("[ERROR] LAB NOT VOCAL\nDaemon is running but vocal=False")
            raise RuntimeError(err)

    return True


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Pytest session start hook to verify boot commit consistency.

    Computes local git commit and fetches served commit from lab-attendant.
    Prints warnings if mismatch or unreachable, OK if match.
    """
    local_commit, served_commit, is_vocal_status = get_bytecode_status()

    # Generate appropriate output
    global _LOCAL_COMMIT, _SERVED_COMMIT, _IS_VOCAL_STATUS
    _LOCAL_COMMIT = local_commit
    _SERVED_COMMIT = served_commit
    _IS_VOCAL_STATUS = is_vocal_status

    if local_commit and served_commit:
        vocal_tag = f" | vocal={is_vocal_status}" if is_vocal_status is not None else ""
        if local_commit == served_commit:
            print(f"✅ boot commit OK: {local_commit}{vocal_tag}")
        else:
            _print_warning_box(
                f"[WARN] STALE BYTECODE\nLocal:  {local_commit}\nServed: {served_commit}{vocal_tag}"
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


_LOCAL_COMMIT: Optional[str] = None
_SERVED_COMMIT: Optional[str] = None
_IS_VOCAL_STATUS: Optional[bool] = None


@pytest.fixture(autouse=True)
def live_bytecode_gate(request):
    """[FEAT-524] LIVE IS GOD Invariant Gate.
    Automatically aborts any test marked with @pytest.mark.live if the served
    lab attendant process on port 8765 is running stale bytecode or is unreachable.
    """
    if request.node.get_closest_marker("live"):
        assert_live_bytecode()


def is_vocal(status_url: str = "http://127.0.0.1:8765/status") -> bool:
    """Direct, single-property source of truth for lab vocality."""
    try:
        resp = requests.get(status_url, timeout=2)
        return resp.status_code == 200 and resp.json().get("vocal", False) is True
    except Exception:
        return False


@pytest.fixture(scope="session")
def live_vocal():
    """Pytest fixture ensuring the lab attendant is reachable, vocal is True,
    and running fresh bytecode matching local git HEAD.
    Fails the test session explicitly if dormant, offline, or running stale bytecode.
    """
    if _LOCAL_COMMIT and _SERVED_COMMIT and _LOCAL_COMMIT != _SERVED_COMMIT:
        pytest.fail(
            f"LIVE IS GOD VIOLATION: Stale bytecode served on port 8765!\n"
            f"Local: {_LOCAL_COMMIT} | Served: {_SERVED_COMMIT}\n"
            f"Action required: 'sudo systemctl restart lab-attendant.service'"
        )

    try:
        resp = requests.get("http://127.0.0.1:8765/status?timeout=60", timeout=60)
        if resp.status_code != 200:
            pytest.fail(f"Lab Attendant status endpoint returned HTTP {resp.status_code}")
        data = resp.json()
        if not data.get("vocal", False):
            pytest.fail(f"Lab is not in vocal state (state={data.get('state')}, vocal={data.get('vocal')})")
        return data
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Lab Attendant unreachable on port 8765: {e}")


def _print_warning_box(message: str):
    """Print ASCII box with warning message."""
    lines = message.split('\n')
    max_len = max(len(line) for line in lines)
    border = "=" * (max_len + 4)
    print(border)
    for line in lines:
        print(f"| {line.ljust(max_len)} |")
    print(border)
