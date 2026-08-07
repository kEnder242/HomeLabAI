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

OVERRIDE_DIR="/etc/systemd/system/sshd.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"

# (1) Write the drop-in (idempotent overwrite).
sudo mkdir -p "${OVERRIDE_DIR}"
sudo tee "${OVERRIDE_FILE}" >/dev/null <<'EOF'
[Service]
OOMScoreAdjust=-1000
MemoryMin=256M
CPUSchedulingPolicy=rr
EOF

# (2) Best-effort daemon-reload so systemd picks up the new drop-in.
#     NOTE: a full `sudo systemctl restart sshd` may still be needed for the
#     new OOM/CPU settings to apply to the running sshd process — restart it
#     at a safe time (it will drop active SSH sessions).
if ! sudo systemctl daemon-reload 2>/dev/null; then
    echo "warning: systemctl daemon-reload failed (best-effort; run 'sudo systemctl daemon-reload' manually)" >&2
fi

# (3) Verify the effective values.
if ! actual="$(systemctl show sshd -p OOMScoreAdjust,MemoryMin,CPUSchedulingPolicy)"; then
    echo "FAIL: could not query systemd for the sshd unit" >&2
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
            if [[ "${value}" != "rr" ]]; then
                echo "MISMATCH: CPUSchedulingPolicy expected 'rr' but got '${value}'" >&2
                ok=0
            else
                echo "OK: CPUSchedulingPolicy=${value}"
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