#!/bin/bash
# xorg_fd_logger.sh - Lightweight telemetry tracking open file descriptors for Xorg
LOG_FILE="/home/jallred/Dev_Lab/xorg_fd_usage.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG_FILE")"

for pid in $(pgrep -x Xorg 2>/dev/null); do
    if [ -d "/proc/$pid" ]; then
        user=$(ps -o user= -p "$pid" 2>/dev/null | tr -d ' ')
        fd_count=$(ls -1 "/proc/$pid/fd" 2>/dev/null | wc -l)
        
        # Parse soft and hard limits
        limits=$(grep "Max open files" "/proc/$pid/limits" 2>/dev/null | awk '{print $4 "/" $5}')
        
        # Breakdown of key descriptor types
        sync_files=$(ls -l "/proc/$pid/fd" 2>/dev/null | grep -c "anon_inode:\[sync_file\]")
        drm_fds=$(ls -l "/proc/$pid/fd" 2>/dev/null | grep -c "/dev/dri")
        sockets=$(ls -l "/proc/$pid/fd" 2>/dev/null | grep -c "socket:")
        
        echo "[$TIMESTAMP] PID=$pid USER=$user OPEN_FDS=$fd_count LIMITS=$limits SYNC_FILES=$sync_files DRM_DEVICES=$drm_fds SOCKETS=$sockets" >> "$LOG_FILE"
    fi
done
