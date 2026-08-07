#!/bin/bash
set -u

# earlyoom_pager_notifier.sh — EarlyOOM kill event → Neural Pager ledger bridge.
#
# BKM One-Liner:  (not run manually — earlyoom(1) invokes it via -N/--notify-command)
#   EARLYOOM_PID=1234 EARLYOOM_NAME=firefox EARLYOOM_MEM=4.2 EARLYOOM_SWAP=0.0 \
#     ./earlyoom_pager_notifier.sh
#
# BKM Core Logic:
#   - earlyoom exports EARLYOOM_PID / EARLYOOM_NAME / EARLYOOM_MEM / EARLYOOM_SWAP
#     to the -N notify command whenever it kills a process.
#   - This script appends exactly one CRITICAL record to the Neural Pager ledger
#     (pager_activity.json): index-0 insert, 2000-entry cap, atomic .tmp + mv write.
#
# BKM Trigger:  earlyoom kills the worst OOM offender (RAM < 5%, swap < 10%).
#
# BKM Scars:
#   - earlyoom runs as root → HOME=/root. The ledger path is HARDCODED absolute;
#     never use ~, $HOME, or $USER here (would silently write to /root).
#   - pager_relay.py (BKM-014) is NOT safe to call from this hook: its
#     expanduser("~/Dev_Lab/...") resolves to /root/Dev_Lab/... under root.
#   - Must return fast and never hang (earlyoom does not wait on the notify
#     command): no sleeps, no prompts, and `timeout 10` guards python3.
#   - jq is not guaranteed installed; JSON is built with python3 stdlib json
#     (preferred), falling back to a minimal pure-bash writer.
#
# Idempotent: safe to call repeatedly; each invocation appends one record.

PAGER_FILE="/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json"
PAGER_DIR="$(dirname "${PAGER_FILE}")"

# earlyoom(1) exports these to the notify command; default safely when missing.
EARLYOOM_PID="${EARLYOOM_PID:-unknown}"
EARLYOOM_NAME="${EARLYOOM_NAME:-unknown}"
EARLYOOM_MEM="${EARLYOOM_MEM:-N/A}"
EARLYOOM_SWAP="${EARLYOOM_SWAP:-N/A}"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
MESSAGE="EarlyOOM KILL: pid=${EARLYOOM_PID} name=${EARLYOOM_NAME} mem=${EARLYOOM_MEM} swap=${EARLYOOM_SWAP}"

mkdir -p "${PAGER_DIR}" 2>/dev/null || exit 0

if command -v python3 >/dev/null 2>&1; then
    # Preferred path: stdlib json handles arbitrary process names (quotes/spaces).
    timeout 10 python3 - "${PAGER_FILE}" "${TIMESTAMP}" "${MESSAGE}" 2>/dev/null <<'PYEOF' || exit 0
import json
import os
import sys

path, ts, msg = sys.argv[1], sys.argv[2], sys.argv[3]

data = []
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []  # corrupted/unparseable -> start fresh, never crash

data.insert(0, {
    "timestamp": ts,
    "severity": "CRITICAL",
    "source": "EarlyOOM",
    "message": msg,
})
data = data[:2000]

tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, path)
PYEOF
else
    # Minimal pure-bash fallback (python3 unavailable). Assumes the ledger is a
    # JSON array in the indent=2 shape (one record per 6 lines). Corruption-safe:
    # content that is not a bracketed array starts a fresh ledger.
    json_escape() {
        local s="$1" out="" c
        local i
        for ((i = 0; i < ${#s}; i++)); do
            c="${s:i:1}"
            case "${c}" in
                '"')  out+='\"' ;;
                '\')  out+='\\' ;;
                $'\t') out+='\t' ;;
                $'\n') out+='\n' ;;
                $'\r') out+='\r' ;;
                *)     out+="${c}" ;;
            esac
        done
        printf '%s' "${out}"
    }

    tmp="${PAGER_FILE}.tmp"
    if [[ -f "${PAGER_FILE}" ]] \
        && [[ "$(head -c 1 "${PAGER_FILE}" 2>/dev/null)" == "[" ]] \
        && [[ "$(tail -c 1 "${PAGER_FILE}" 2>/dev/null)" == "]" ]]; then
        # Existing well-formed array: strip outer brackets, prepend new record.
        {
            printf '[\n'
            printf '  {\n'
            printf '    "timestamp": "%s",\n' "$(json_escape "${TIMESTAMP}")"
            printf '    "severity": "CRITICAL",\n'
            printf '    "source": "EarlyOOM",\n'
            printf '    "message": "%s"\n' "$(json_escape "${MESSAGE}")"
            printf '  },\n'
            sed '1d;$d' "${PAGER_FILE}"
        } > "${tmp}"
    else
        # Corrupt or missing ledger: start fresh with a single record.
        {
            printf '[\n'
            printf '  {\n'
            printf '    "timestamp": "%s",\n' "$(json_escape "${TIMESTAMP}")"
            printf '    "severity": "CRITICAL",\n'
            printf '    "source": "EarlyOOM",\n'
            printf '    "message": "%s"\n' "$(json_escape "${MESSAGE}")"
            printf '  }\n'
            printf ']\n'
        } > "${tmp}"
    fi

    # Best-effort 2000-entry cap (each indent=2 record opens with "  {").
    awk '/^  \{/ { n++ } n <= 2000 || /^\]/ { print }' "${tmp}" > "${tmp}.cap" 2>/dev/null \
        && mv -f "${tmp}.cap" "${tmp}" 2>/dev/null

    mv -f "${tmp}" "${PAGER_FILE}" 2>/dev/null || rm -f "${tmp}"
fi

exit 0