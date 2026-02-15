# BKM: Strategic Patching (Unified Diffs)

## 🎯 Objective
To modify codebase files with high precision, avoiding the brittleness of literal string replacement.

## 🛠️ Execution Protocol (Safe Scalpel v3.0)
1. **Context Discovery**: Use `read_file` to identify the target code block.
2. **Choose Mode**:
    - **Block Mode (Preferred)**: Use the Search/Replace block format for high readability.
    - **Diff Mode**: Use standard Unified Diffs for large, granular changes.
3. **Apply**: Execute via CLI: `python3 scalpel.py <file> <mode> <content>`.
4. **Safety**: The tool provides a **Live Diff Preview** and runs a **Mandatory Lint-Gate** (Python/JS) before committing.

## 💎 Why it is a "Gem"
- **Indentation Immune**: Handles tabs/spaces gracefully.
- **Context Aware**: Only modifies the targeted "hunk," reducing the risk of accidental global changes.
- **Atomic**: The patch utility either succeeds completely or fails with a `.rej` file, preventing partial "mutilation" of source code.

## ⚠️ Lessons Learned (Feb 2026)
- **Break it Down**: Large patches often fail due to slight context shifts. Break changes into small, atomic hunks (e.g., Imports first, then Methods).
- **Verify Context**: Always use `read_file` to confirm exact line content before drafting a patch.
- **Offset Awareness**: `patch` can handle slight line offsets, but not character mismatches in context lines. Keep context lines simple.
