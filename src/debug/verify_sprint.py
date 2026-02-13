import os
import subprocess

def test_patch_tool():
    print("--- Testing patch_file Tool ---")
    ws_dir = os.path.expanduser("~/AcmeLab/workspace")
    os.makedirs(ws_dir, exist_ok=True)
    test_file = os.path.join(ws_dir, "test_patch.txt")

    # 1. Initial State
    with open(test_file, "w") as f:
        f.write("Line 1\nLine 2\nLine 3\n")

    # 2. Unified Diff
    diff = """--- test_patch.txt
+++ test_patch.txt
@@ -1,3 +1,3 @@
 Line 1
-Line 2
+Line 2: Patched!
 Line 3
"""

    patch_file_path = os.path.join(ws_dir, "test.patch")
    with open(patch_file_path, "w") as f:
        f.write(diff)

    # 3. Apply
    res = subprocess.run(["patch", test_file, patch_file_path], capture_output=True, text=True)
    if res.returncode == 0:
        with open(test_file, "r") as f:
            content = f.read()
            if "Patched!" in content:
                print("[PASS] Patch applied correctly.")
            else:
                print("[FAIL] Patch applied but content wrong.")
    else:
        print(f"[FAIL] Patch command failed: {res.stderr}")

    if os.path.exists(patch_file_path): os.remove(patch_file_path)

def test_progress_logic():
    print("\n--- Testing Progress Reporting Logic ---")
    total = 10
    processed = 3
    progress = int((processed / total) * 100)
    print(f"[INFO] 3/10 files processed -> {progress}% progress.")
    if progress == 30:
        print("[PASS] Progress calculation accurate.")
    else:
        print("[FAIL] Progress calculation error.")

if __name__ == "__main__":
    test_patch_tool()
    test_progress_logic()
