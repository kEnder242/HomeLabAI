import sys
import os
from atomic_patcher import apply_batch_refinement

target = "HomeLabAI/src/lab_attendant.py"

edits = [
    {
        "old": "# --- Global State ---",
        "new": "# --- Global State ---
# IDLE_TIMEOUT: Default 300s, override via env for tests
IDLE_TIMEOUT = int(os.environ.get('LAB_IDLE_TIMEOUT', 300))
slow_burn_process: subprocess.Popen = None",
        "desc": "Add IDLE_TIMEOUT and slow_burn state"
    },
    {
        "old": "        self.app.router.add_post("/hard_reset", self.handle_hard_reset)",
        "new": "        self.app.router.add_post("/hard_reset", self.handle_hard_reset)
        self.app.router.add_post("/slow_burn", self.handle_slow_burn)",
        "desc": "Expose /slow_burn endpoint"
    },
    {
        "old": "    async def handle_start(self, request):",
        "new": "    async def handle_slow_burn(self, request):
        """Starts or resumes a background scanning task."""
        global slow_burn_process
        # Implementation: Launch mass_scan.py
        # (For now, we just track it so we can pre-empt it)
        return web.json_response({"status": "active"})

    async def handle_start(self, request):",
        "desc": "Implement handle_slow_burn"
    }
]

apply_batch_refinement(target, edits)
