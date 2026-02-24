import subprocess
import os
import sys
import shutil

def lint_file(file_path):
    """Detects type and runs appropriate linter."""
    if file_path.endswith(".py"):
        ruff_path = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/ruff"
        # [SWEET SPOT] Ignore E501 (Line length) to focus on logic and imports
        res = subprocess.run([ruff_path, "check", file_path, "--select", "E,F,W", "--ignore", "E501"], 
                             capture_output=True, text=True)
        return res.returncode == 0, res.stdout + res.stderr
    elif file_path.endswith(".js"):
        res = subprocess.run(["eslint", file_path, "--quiet"], 
                             capture_output=True, text=True)
        return res.returncode == 0, res.stdout + res.stderr
    return True, ""

def apply_batch_refinement(target_file, edits):
    """
    Applies a batch of edits and lints only at the end.
    edits: List of dictionaries {"old": str, "new": str, "desc": str}
    No rollback on failure; lint serves as a reminder only.
    """
    print(f"--- 🛡️ Safe-Scalpel [BATCH MODE]: {target_file} ---")
    
    with open(target_file, "r") as f:
        original_content = f.read()
    
    current_content = original_content
    backup_file = target_file + ".bak"
    shutil.copy(target_file, backup_file)

    success_count = 0
    for i, edit in enumerate(edits):
        old_str = edit["old"]
        new_str = edit["new"]
        desc = edit.get("desc", f"Edit {i}")
        
        if old_str not in current_content:
            print(f"[SKIP] {desc}: 'old_string' not found.")
            continue
            
        current_content = current_content.replace(old_str, new_str, 1)
        success_count += 1
        print(f"[APPLY] {desc}")

    if success_count == 0:
        print("[CANCEL] No edits were applicable.")
        os.remove(backup_file)
        return False

    # Write the batch state
    with open(target_file, "w") as f:
        f.write(current_content)
            
    print(f"\n[VERIFY] All {success_count} edits applied. Running final lint-gate...")
    passed, errors = lint_file(target_file)
    
    if not passed:
        print("--- ⚠️ LINT WARNINGS DETECTED ---")
        print(errors)
        print("[NOTE] Changes persisted. Please address the lint issues manually.")
    else:
        print("[PASS] File is lint-clean.")
    
    print("[DONE] Refinement committed.")
    os.remove(backup_file)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: atomic_patcher.py <target_file> <desc> <old_text> <new_text>")
        sys.exit(1)
    
    target_file = sys.argv[1]
    
    # Simple CLI mode for single edits
    if len(sys.argv) == 5:
        desc = sys.argv[2]
        old_text = sys.argv[3]
        new_text = sys.argv[4]
        edits = [{"old": old_text, "new": new_text, "desc": desc}]
        apply_batch_refinement(target_file, edits)
    else:
        print("Safe-Scalpel Batch Library Ready.")
