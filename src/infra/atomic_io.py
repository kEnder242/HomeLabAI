import os
import json
import logging
import tempfile

def atomic_write_json(path: str, data: any, indent: int = 2):
    """
    [FEAT-180] Atomic Write: Implements the .tmp + os.replace pattern 
    to prevent 0-byte or corrupted JSON files during system crashes.
    """
    path = os.path.expanduser(path)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    
    # Use the same directory for the temp file to ensure it's on the same partition (required for os.replace)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=indent)
            f.flush()
            os.fsync(f.fileno()) # Force write to physical silicon
        
        os.replace(tmp_path, path)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        logging.error(f"[ATOMIC] Failed to write {path}: {e}")
        raise

def atomic_write_text(path: str, content: str):
    """Atomic write for plain text/markdown files."""
    path = os.path.expanduser(path)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        
        os.replace(tmp_path, path)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        logging.error(f"[ATOMIC] Failed to write {path}: {e}")
        raise
