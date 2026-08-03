import os
import sys
import re
import subprocess
import argparse

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
        elif ext == ".html":
            return _lint_html_inline_js(file_path)
        return True, ""
    except Exception as e:
        return False, str(e)

def _lint_html_inline_js(file_path):
    """Extract inline <script> blocks (no src attr, non-empty) and node --check each."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except Exception as e:
        return False, f"HTML read failed: {e}"
    blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', content, re.S | re.I)
    errors = []
    checked = 0
    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        checked += 1
        tmp = f"{file_path}.block{i}.js"
        try:
            with open(tmp, "w") as f:
                f.write(block)
            res = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            if res.returncode != 0:
                errors.append(f"<script> block #{i}: {res.stderr.strip()}")
        except Exception as e:
            errors.append(f"<script> block #{i}: check error {e}")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    if errors:
        return False, f"HTML inline-JS syntax errors ({checked} checked):\n" + "\n".join(errors)
    return True, f"HTML inline-JS OK ({checked} non-empty inline <script> blocks checked)."

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
