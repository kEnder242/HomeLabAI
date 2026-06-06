import os
import sys
import subprocess
import argparse
import re

def run_ruff(file_path):
    """Run ruff check on the file and return True if it passes."""
    try:
        ruff_bin = "HomeLabAI/.venv/bin/ruff"
        if not os.path.exists(ruff_bin):
            ruff_bin = "ruff"
            
        result = subprocess.run([ruff_bin, "check", file_path], capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def atomic_patch(file_path, old_pattern, new_pattern, multi=False):
    """Apply a regex-based patch only if it results in a lint-clean file."""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False

    with open(file_path, "r") as f:
        content = f.read()

    # We use re.sub with groups to preserve indentation
    # If the user provides a raw string, we'll try to match it literally first
    count = len(re.findall(old_pattern, content, re.MULTILINE))
    if count == 0:
        print(f"Error: Pattern not found in {file_path}.")
        return False

    if not multi and count > 1:
        print(f"Error: Multiple occurrences ({count}) found. Use --multi.")
        return False

    new_content = re.sub(old_pattern, new_pattern, content, flags=re.MULTILINE)
    
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(new_content)

    ok, logs = run_ruff(tmp_path)
    if ok:
        os.replace(tmp_path, file_path)
        print(f"Successfully patched {file_path} and verified with ruff.")
        return True
    else:
        print(f"Error: Patch failed linting.\n{logs}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regex-based atomic, lint-gated file patcher.")
    parser.add_argument("--file", required=True, help="File to patch")
    parser.add_argument("--old", required=True, help="Regex pattern to find")
    parser.add_argument("--new", required=True, help="Regex replacement (supports \1, \2 etc)")
    parser.add_argument("--multi", action="store_true", help="Replace all occurrences")
    
    args = parser.parse_args()
    
    # regex sub handles escaped newlines differently, but we still need to convert the raw args
    new_pattern = args.new.replace("\\n", "\n")
    old_pattern = args.old.replace("\\n", "\n")
    
    if atomic_patch(args.file, old_pattern, new_pattern, args.multi):
        sys.exit(0)
    else:
        sys.exit(1)
