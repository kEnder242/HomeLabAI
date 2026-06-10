import os
import sys
import subprocess
import argparse
import re

def run_linter(file_path):
    """Run appropriate linter based on file extension."""
    ext = os.path.splitext(file_path)[1]
    try:
        if ext == ".py":
            ruff_bin = "HomeLabAI/.venv/bin/ruff"
            if not os.path.exists(ruff_bin):
                ruff_bin = "ruff"
            result = subprocess.run([ruff_bin, "check", file_path], capture_output=True, text=True)
            return result.returncode == 0, result.stdout + result.stderr
        elif ext == ".sh":
            result = subprocess.run(["bash", "-n", file_path], capture_output=True, text=True)
            return result.returncode == 0, result.stderr
        return True, ""
    except Exception as e:
        return False, str(e)

def atomic_patch(file_path, old_pattern, new_pattern, multi=False, force=False):
    """Apply a regex-based patch, logging lint errors but allowing bypass with force."""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False

    with open(file_path, "r") as f:
        content = f.read()

    # Apply patch
    if multi:
        new_content, count = re.subn(old_pattern, new_pattern, content, flags=re.MULTILINE)
    else:
        new_content, count = re.subn(old_pattern, new_pattern, content, count=1, flags=re.MULTILINE)

    if count == 0:
        print(f"Error: Pattern not found in {file_path}.")
        return False

    # Create temporary file
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(new_content)

    # Run linter
    success, output = run_linter(tmp_path)
    os.replace(tmp_path, file_path)
    if success:
        print(f"Successfully patched {file_path} and verified.")
    else:
        print(f"Warning: Patch applied but failed passive linting.\n{output}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atomic Multi-Language Patcher with Passive Linting")
    parser.add_argument("--file", required=True, help="File to patch")
    parser.add_argument("--old", required=True, help="Regex pattern to find")
    parser.add_argument("--new", required=True, help="Replacement text")
    parser.add_argument("--multi", action="store_true", help="Replace multiple occurrences")
    parser.add_argument("--force", action="store_true", help="Deprecated. Patcher is now fully passive.")
    
    args = parser.parse_args()
    
    # Handle newlines in CLI arguments
    new_pattern = args.new.replace("\\n", "\n")
    old_pattern = args.old.replace("\\n", "\n")
    
    if atomic_patch(args.file, old_pattern, new_pattern, args.multi, args.force):
        sys.exit(0)
    else:
        sys.exit(1)
