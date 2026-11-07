#!/usr/bin/env bash
# ==============================================================================
# Transparent Backward-Compatibility Shim (start_vllm.sh)
# Framework Anchor: [LAB-122] Zero-Host Hybrid Inference Standard
# Sprint Anchor   : SPRINT_PLAN_SPR_111_0 (Story 111.13)
# Protocols       : BKM-044 (Attendant Authority Gate), BKM-018
#
# Delegates canonical lifecycle execution to src/engine_ctl.sh.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_CTL="$SCRIPT_DIR/engine_ctl.sh"

# [BKM-044] Attendant Authority Gate: Direct invocation is forbidden without authority
if [[ -z "${LAB_ATTENDANT_SPAWN:-}" ]] && [[ "${1:-}" != "--force" ]]; then
    echo "❌ [BKM-044] ERROR: Direct engine ignition is forbidden." >&2
    echo "👉 Transition state via Lab Attendant API: curl -X POST http://127.0.0.1:8765/wake" >&2
    echo "💡 To override for manual silicon debugging, pass --force." >&2
    exit 1
fi

# Filter out --force from arguments passed to engine_ctl.sh
ARGS=()
for arg in "$@"; do
    if [[ "$arg" != "--force" ]]; then
        ARGS+=("$arg")
    fi
done

echo "🔗 [SHIM] start_vllm.sh delegating to $ENGINE_CTL start ${ARGS[*]:-}"
exec "$ENGINE_CTL" start "${ARGS[@]:-}"
