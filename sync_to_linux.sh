#!/bin/bash
# Syncs the current directory to the VoiceGateway folder on z87-Linux
# Excludes heavy local folders like .venv or git
# Usage: ./sync_to_linux.sh

TARGET_HOST="jallred@z87-Linux.local"
TARGET_DIR="~/AcmeLab/"

echo "Syncing to $TARGET_HOST:$TARGET_DIR ..."
rsync -avz --delete -e "ssh -i ~/.ssh/id_rsa_wsl" \
    --exclude '.venv' \
    --exclude '.git' \
    --exclude 'logs' \
    --exclude 'chroma_db' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'tmp_unzip_dir_for_rclone' \
    ./ "$TARGET_HOST:$TARGET_DIR"

echo "Sync Complete."

