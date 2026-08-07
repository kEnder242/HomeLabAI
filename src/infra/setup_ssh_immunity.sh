#!/bin/bash
set -euo pipefail

# setup_ssh_immunity.sh — harden sshd against OOM kills and CPU starvation.
#
# Installs a systemd drop-in for sshd.service that:
#   - makes sshd OOM-immune (OOMScoreAdjust=-1000)
#   - reserves 256M of memory (MemoryMin=256M)
#   - grants realtime CPU scheduling (CPUSchedulingPolicy=rr)
#
# Idempotent: safe to re-run; the drop-in is overwritten each time.

# Determine active service name (ssh on Debian/Ubuntu, sshd on RHEL/Fedora)
SERVICE_NAME="ssh"
if systemctl list-unit-files | grep -q "sshd.service"; then
    SERVICE_NAME="sshd"
fi

OVERRIDE_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"

# Also write sshd alias directory if different
ALT_DIR="/etc/systemd/system/sshd.service.d"
if [[ "${SERVICE_NAME}" == "ssh" ]]; then
    ALT_DIR="/etc/systemd/system/sshd.service.d"
else
    ALT_DIR="/etc/systemd/system/ssh.service.d"
fi

# (1) Write the drop-in (idempotent overwrite).
sudo mkdir -p "${OVERRIDE_DIR}" "${ALT_DIR}"
sudo tee "${OVERRIDE_FILE}" "${ALT_DIR}/override.conf" >/dev/null <<'EOF'
[Service]
OOMScoreAdjust=-1000
MemoryMin=256M
CPUSchedulingPolicy=rr
EOF

# (2) Daemon-reload and restart active service
sudo systemctl daemon-reload || true
sudo systemctl restart "${SERVICE_NAME}" || true

# (3) Verify the effective values.
if ! actual="$(systemctl show "${SERVICE_NAME}" -p OOMScoreAdjust,MemoryMin,CPUSchedulingPolicy)"; then
    echo "FAIL: could not query systemd for the ${SERVICE_NAME} unit" >&2
    exit 1
fi

ok=1
while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    case "${key}" in
        OOMScoreAdjust)
            if [[ "${value}" != "-1000" ]]; then
                echo "MISMATCH: OOMScoreAdjust expected '-1000' but got '${value}'" >&2
                ok=0
            else
                echo "OK: OOMScoreAdjust=${value}"
            fi
            ;;
        MemoryMin)
            # systemctl show reports MemoryMin in raw bytes (256M = 268435456).
            if [[ "${value}" != "256M" && "${value}" != "268435456" ]]; then
                echo "MISMATCH: MemoryMin expected '256M' but got '${value}'" >&2
                ok=0
            else
                echo "OK: MemoryMin=${value}"
            fi
            ;;
        CPUSchedulingPolicy)
            if [[ "${value}" != "rr" && "${value}" != "2" ]]; then
                echo "MISMATCH: CPUSchedulingPolicy expected 'rr' or '2' but got '${value}'" >&2
                ok=0
            else
                echo "OK: CPUSchedulingPolicy=${value} (SCHED_RR)"
            fi
            ;;
    esac
done <<< "${actual}"

if (( ok == 1 )); then
    echo "SUCCESS: sshd is OOM-immune with MemoryMin=256M and realtime CPU scheduling"
    exit 0
else
    echo "FAIL: sshd hardening not fully applied (see mismatches above; 'sudo systemctl restart sshd' may be required)" >&2
    exit 1
fi