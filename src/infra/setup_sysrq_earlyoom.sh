#!/bin/bash
set -euo pipefail

# setup_sysrq_earlyoom.sh — Kernel SysRq Emergency Protocol & EarlyOOM Sentinel.
#
# BKM One-Liner:  sudo ./setup_sysrq_earlyoom.sh
#
# BKM Core Logic:
#   - kernel.sysrq = 1            -> enables Magic SysRq emergency key combos
#                                    (e.g. Alt+SysRq+REISUB reboot, OOM-kill).
#   - earlyoom sentinel           -> kills the worst OOM offender when available
#                                    RAM < 5% and available swap < 10%
#                                    (EARLYOOM_ARGS="--mem 5 --swap 10").
#
# BKM Trigger:  OOM freeze / unresponsive host under memory pressure; run during
#               infra hardening to guarantee a recovery path (SysRq) and an
#               OOM pre-emptor (earlyoom) before the kernel OOM killer stalls.
#
# BKM Scars:
#   - earlyoom may be uninstallable (no apt, no distro package); warn and let
#     the final verification report the honest FAIL instead of aborting early.
#   - A systemd drop-in Environment= is applied after EnvironmentFile=, so it
#     overrides /etc/default/earlyoom on Debian-family distros.
#   - sysctl -p is best-effort; the value also applies on next boot.
#
# Idempotent: safe to re-run; both config files are overwritten each time.

SYSRQ_CONF="/etc/sysctl.d/99-sysrq.conf"
EARLYOOM_DROPIN_DIR="/etc/systemd/system/earlyoom.service.d"
EARLYOOM_DROPIN="${EARLYOOM_DROPIN_DIR}/override.conf"

# (1) Write the sysrq sysctl (idempotent overwrite).
sudo tee "${SYSRQ_CONF}" >/dev/null <<'EOF'
kernel.sysrq = 1
EOF

# (2) Best-effort apply immediately; the value also applies on next boot.
if ! sudo sysctl -p "${SYSRQ_CONF}" 2>/dev/null; then
    echo "warning: sysctl -p failed (best-effort; value applies on next boot)" >&2
fi

# (3) Install earlyoom if missing (best-effort; warn, do not abort).
if ! command -v earlyoom >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq >/dev/null 2>&1 || true
        if ! sudo apt-get install -y earlyoom; then
            echo "warning: apt-get install earlyoom failed (install manually; verification below will FAIL)" >&2
        fi
    else
        echo "warning: earlyoom not found and no apt-get available (install manually; verification below will FAIL)" >&2
    fi
fi

# (4) Write the earlyoom systemd drop-in (idempotent overwrite).
#     EARLYOOM_ARGS flag semantics (earlyoom(1)):
#       --mem PERCENT   kill when available RAM falls below PERCENT (default 10)
#       --swap PERCENT  kill when available swap falls below PERCENT (default 10)
#       --prefer/--avoid: bias which processes are killed (intentionally omitted;
#                         keep the sentinel simple and distro-agnostic).
sudo mkdir -p "${EARLYOOM_DROPIN_DIR}"
sudo tee "${EARLYOOM_DROPIN}" >/dev/null <<'EOF'
[Service]
Environment=EARLYOOM_ARGS=--mem 5 --swap 10
EOF

# (5) Best-effort daemon-reload + enable + restart so the drop-in applies.
#     restart covers both a fresh install (starts the unit) and an already
#     running daemon (re-applies the new EARLYOOM_ARGS).
if ! sudo systemctl daemon-reload 2>/dev/null; then
    echo "warning: systemctl daemon-reload failed (best-effort)" >&2
fi
if ! sudo systemctl enable earlyoom 2>/dev/null; then
    echo "warning: systemctl enable earlyoom failed (is earlyoom installed?)" >&2
fi
if ! sudo systemctl restart earlyoom 2>/dev/null; then
    echo "warning: systemctl restart earlyoom failed (is earlyoom installed?)" >&2
fi

# (6) Verify the effective values.
if ! actual="kernel.sysrq=$(sysctl -n kernel.sysrq 2>/dev/null || echo 'unavailable')
earlyoom_active=$(systemctl is-active earlyoom 2>/dev/null || echo 'unavailable')
earlyoom_enabled=$(systemctl is-enabled earlyoom 2>/dev/null || echo 'unavailable')"; then
    echo "FAIL: could not query sysctl/systemd for verification values" >&2
    exit 1
fi

if [[ -z "${actual}" ]]; then
    echo "FAIL: no verification values returned (sysctl/systemd query failed)" >&2
    exit 1
fi

ok=1
while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    case "${key}" in
        kernel.sysrq)
            if [[ "${value}" != "1" ]]; then
                echo "MISMATCH: kernel.sysrq expected '1' but got '${value}'" >&2
                ok=0
            else
                echo "OK: kernel.sysrq=${value}"
            fi
            ;;
        earlyoom_active)
            if [[ "${value}" != "active" ]]; then
                echo "MISMATCH: earlyoom expected 'active' but got '${value}'" >&2
                ok=0
            else
                echo "OK: earlyoom is-active=${value}"
            fi
            ;;
        earlyoom_enabled)
            if [[ "${value}" != "enabled" ]]; then
                echo "MISMATCH: earlyoom expected 'enabled' but got '${value}'" >&2
                ok=0
            else
                echo "OK: earlyoom is-enabled=${value}"
            fi
            ;;
    esac
done <<< "${actual}"

if (( ok == 1 )); then
    echo "SUCCESS: kernel.sysrq=1 (Magic SysRq) and earlyoom sentinel active (--mem 5 --swap 10)"
    exit 0
else
    echo "FAIL: SysRq/earlyoom hardening not fully applied (see mismatches above)" >&2
    exit 1
fi