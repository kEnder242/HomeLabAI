#!/bin/bash
# Syncs the local src/mic_test.py to the Linux host, 
# then moves it to the GDrive mount for Windows to pick up.

TARGET_HOST="jallred@z87-Linux.local"
REMOTE_SRC="~/AcmeLab/src/mic_test.py"
GDRIVE_DEST="~/knowledge_base/HomeLabAIProject/src/mic_test.py"

# Step 1: Sync to Linux (standard workflow)
./sync_to_linux.sh

# Step 2: Copy to GDrive mount on Linux
echo "Deploying to GDrive for Windows..."
ssh -i ~/.ssh/id_rsa_wsl "$TARGET_HOST" "cp $REMOTE_SRC $GDRIVE_DEST"

echo "Success! mic_test.py is now available in Google Drive for Windows."
