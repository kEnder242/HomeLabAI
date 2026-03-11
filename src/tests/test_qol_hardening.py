import pytest
import os
import json
import tempfile
from infra.atomic_io import atomic_write_json, atomic_write_text

def test_atomic_write_json():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "test.json")
        data = {"key": "value"}
        
        atomic_write_json(path, data)
        
        with open(path, "r") as f:
            loaded = json.load(f)
        assert loaded == data
        
        # Test overwrite
        new_data = {"key2": "value2"}
        atomic_write_json(path, new_data)
        with open(path, "r") as f:
            loaded = json.load(f)
        assert loaded == new_data

def test_atomic_write_text():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "test.txt")
        content = "hello world"
        
        atomic_write_text(path, content)
        
        with open(path, "r") as f:
            loaded = f.read()
        assert loaded == content
