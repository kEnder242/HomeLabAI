#!/bin/bash
# Usage: ./release.sh <new_version>
# Example: ./release.sh 2.0.1

if [ -z "$1" ]; then
    echo "Usage: ./release.sh <new_version>"
    exit 1
fi

NEW_VER="$1"
echo "🚀 Bumping version to $NEW_VER..."

if [ ! -f "src/acme_lab.py" ]; then
    echo "❌ Error: Could not find src/acme_lab.py. Run from project root."
    exit 1
fi

# Update Python Files (Safe non-greedy regex)
FILES=("src/acme_lab.py" "src/intercom.py" "src/mic_test.py")

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   Updating $file..."
        sed -i "s/^VERSION = .*/VERSION = \"$NEW_VER\"/" "$file"
    else
        echo "⚠️  Warning: $file not found."
    fi
done

# Update Test Scripts (Handshakes)
TEST_FILES=("src/test_intercom_flow.py" "src/test_memory_integration.py" "src/test_shutdown.py")
for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   Updating handshake in $file..."
        sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/" "$file"
    fi
done

echo "✅ Version bumped to $NEW_VER."

# --- NEW: Deploy to Google Drive for Windows ---
GDRIVE_DEST="~/knowledge_base/HomeLabAIProject/src/intercom.py"
echo "🚀 Deploying intercom.py to Google Drive..."
cp src/intercom.py $(eval echo $GDRIVE_DEST)
echo "✅ Deployment complete."

echo "👉 Now run: git commit -am \"chore: Release v$NEW_VER\""
