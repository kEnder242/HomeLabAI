# BKM: Strategic Patching (Unified Diffs)

## 🎯 Objective
To modify codebase files with high precision, avoiding the brittleness of literal string replacement.

## 🛠️ Execution Protocol
1. **Context Discovery**: Use `read_file` to identify the target lines and surrounding context.
2. **Draft Patch**: Create a Unified Diff (`.patch`) file using the standard `diff -u` format.
3. **Apply**: Execute via shell: `patch <target_file> <patch_file>`.
4. **Validation**: Run the relevant integration test or `verify_sprint.py`.

## 💎 Why it is a "Gem"
- **Indentation Immune**: Handles tabs/spaces gracefully.
- **Context Aware**: Only modifies the targeted "hunk," reducing the risk of accidental global changes.
- **Atomic**: The patch utility either succeeds completely or fails with a `.rej` file, preventing partial "mutilation" of source code.
