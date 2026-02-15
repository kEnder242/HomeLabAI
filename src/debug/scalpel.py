import os
import sys
import subprocess
import shutil
import difflib
import re

# --- Configuration ---
RUFF_PATH = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/ruff"
ESLINT_PATH = "/usr/bin/eslint"

def lint_file(file_path):
    """Runs appropriate linter and returns (passed, output)."""
    if file_path.endswith(".py"):
        res = subprocess.run([RUFF_PATH, "check", file_path, "--select", "E,F,W"], 
                             capture_output=True, text=True)
        return res.returncode == 0, res.stdout + res.stderr
    elif file_path.endswith(".js"):
        # Check if config exists, fallback to basic if not
        config_path = os.path.join(os.path.dirname(file_path), ".eslintrc.json")
        cmd = [ESLINT_PATH, file_path, "--quiet"]
        if not os.path.exists(config_path):
            # Minimal inline config if none exists
            cmd.extend(["--no-eslintrc", "--env", "browser,es2020", "--parser-options", "ecmaVersion:12"])
        
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0, res.stdout + res.stderr
    return True, "No linter defined for this file type."

def apply_search_replace(content, search_block, replace_block):
    """Applies a single Aider-style search/replace block."""
    if search_block not in content:
        return None, "Search block not found exactly in file."
    
    new_content = content.replace(search_block, replace_block, 1)
    return new_content, None

def apply_unified_diff(path, diff_text):
    """Applies a standard unified diff using the system patch tool."""
    temp_patch = path + ".patch"
    with open(temp_patch, 'w') as f:
        f.write(diff_text)
    
    res = subprocess.run(["patch", "-u", path, temp_patch], capture_output=True, text=True)
    os.remove(temp_patch)
    
    if res.returncode == 0:
        return True, res.stdout
    return False, res.stderr

def print_diff(old_content, new_content, filename):
    """Prints a human-readable diff to STDOUT."""
    print(f"\n--- 📋 PREVIEW: {filename} ---")
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    )
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            print(f"\033[32m{line.strip()}\033[0m") # Green
        elif line.startswith('-') and not line.startswith('---'):
            print(f"\033[31m{line.strip()}\033[0m") # Red
        else:
            print(line.strip())
    print("--- END PREVIEW ---\n")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scalpel.py <target_file> <mode: diff|block> <content>")
        sys.exit(1)

    path = sys.argv[1]
    mode = sys.argv[2].lower()
    raw_content = sys.argv[3]

    if not os.path.exists(path):
        print(f"❌ Error: File '{path}' not found.")
        sys.exit(1)

    with open(path, 'r') as f:
        original_content = f.read()

    new_content = None
    error = None

    if mode == "block":
        # Parse Aider-style: <<<< SEARCH \n ... \n ==== \n ... \n >>>> REPLACE
        pattern = r"<<<<<< SEARCH\n(.*?)\n======\n(.*?)\n>>>>>> REPLACE"
        match = re.search(pattern, raw_content, re.DOTALL)
        if not match:
            print("❌ Error: Invalid block format. Use <<<<<< SEARCH ... ====== ... >>>>>> REPLACE")
            sys.exit(1)
        
        search_text = match.group(1)
        replace_text = match.group(2)
        new_content, error = apply_search_replace(original_content, search_text, replace_text)
    
    elif mode == "diff":
        # Apply unified diff
        success, msg = apply_unified_diff(path, raw_content)
        if success:
            with open(path, 'r') as f:
                new_content = f.read()
        else:
            error = msg

    if error:
        print(f"❌ Patch Failed: {error}")
        sys.exit(1)

    # Preview and Lint
    print_diff(original_content, new_content, os.path.basename(path))
    
    # Temporarily write to check lint
    with open(path, 'w') as f:
        f.write(new_content)
    
    print("🛡️ Running Lint-Gate...")
    passed, lint_msg = lint_file(path)
    
    if not passed:
        print("💥 LINT REGRESSION DETECTED!")
        print(lint_msg)
        print("⏪ Rolling back changes.")
        with open(path, 'w') as f:
            f.write(original_content)
        sys.exit(1)

    print("✅ Strategic patch applied and lint-verified.")

if __name__ == "__main__":
    main()
