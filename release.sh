#!/bin/bash
# Usage: ./release.sh <new_version>
# Example: ./release.sh 2.0.1

if [ -z "$1" ]; then
    echo "Usage: ./release.sh <new_version>"
    exit 1
fi

NEW_VER="$1"
echo "🚀 Bumping version to $NEW_VER..."

# 1. Update Source of Truth (if we used a VERSION file, but we'll just track it for now)
# We will just verify we are in the root
if [ ! -f "src/acme_lab.py" ]; then
    echo "❌ Error: Could not find src/acme_lab.py. Run from project root."
    exit 1
fi

# 2. Update Python Files
# Regex looks for: VERSION = "..."
# We use perl for safer regex handling across platforms, or sed.
# Linux sed -i is standard.

FILES=("src/acme_lab.py" "src/intercom.py" "src/mic_test.py")

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   Updating $file..."
        sed -i "s/^VERSION = .*/VERSION = \"$NEW_VER\"/" "$file"
    else
        echo "⚠️  Warning: $file not found."
    fi
done

# 3. Update Test Scripts (Handshakes)
TEST_FILES=("src/test_intercom_flow.py" "src/test_memory_integration.py" "src/test_shutdown.py")
for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   Updating handshake in $file..."
        sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/" "$file"
    fi
done

echo "✅ Version bumped to $NEW_VER."
echo "👉 Now run: git commit -am \"chore: Release v$NEW_VER\""
