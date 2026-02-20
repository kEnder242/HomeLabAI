import logging
import io
import sys
import os

# Ensure we can import acme_lab
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from acme_lab import reclaim_logger

def test_montana_isolation():
    print("--- [TEST] Montana Protocol Verification ---")
    
    # 1. Setup a "hijacked" logger like NeMo might
    nemo_logger = logging.getLogger("nemo")
    nemo_logger.setLevel(logging.DEBUG)
    
    # 2. Trigger the protocol
    reclaim_logger()
    
    # 3. Verify nemo is silenced to ERROR
    print(f"[CHECK] NeMo Level: {logging.getLevelName(nemo_logger.level)}")
    assert nemo_logger.level == logging.ERROR
    
    # 4. Verify Root level is INFO
    root_level = logging.getLogger().level
    print(f"[CHECK] Root Level: {logging.getLevelName(root_level)}")
    assert root_level == logging.INFO
    
    print("✅ Montana Protocol verified: Loggers isolated.")

if __name__ == "__main__":
    try:
        test_montana_isolation()
    except AssertionError as e:
        print(f"❌ Verification Failed: {e}")
        sys.exit(1)
