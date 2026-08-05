import pytest
import requests

def test_version_gate():
    """
    Test that the Lab Attendant exposes boot_commit in both /version and /status endpoints.
    """
    try:
        ver_resp = requests.get("http://127.0.0.1:8765/version", timeout=3)
    except requests.exceptions.RequestException:
        pytest.skip("Lab Attendant unreachable on port 8765")
        
    assert ver_resp.status_code == 200
    
    ver_data = ver_resp.json()
    assert "boot_commit" in ver_data
    assert isinstance(ver_data["boot_commit"], str)
    assert len(ver_data["boot_commit"]) > 0
    
    try:
        stat_resp = requests.get("http://127.0.0.1:8765/status", timeout=3)
    except requests.exceptions.RequestException:
        pytest.skip("Lab Attendant unreachable on port 8765 for /status")
        
    assert stat_resp.status_code == 200
    
    stat_data = stat_resp.json()
    assert "boot_commit" in stat_data
