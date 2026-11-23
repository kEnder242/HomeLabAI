# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
from atomic_patcher import apply_batch_refinement

target = "HomeLabAI/src/acme_lab.py"

edits = [
    {
        "old": "    def is_user_typing(self):",
        "new": "    async def sim_time_warp(self, s):\n        self.last_activity -= s\n        logging.info(f'[DEBUG] Warped -{s}s')\n\n    def is_user_typing(self):",
        "desc": "Add sim_time_warp",
    },
    {
        "old": '                    elif msg_type == "workspace_save":',
        "new": '                    elif msg_type == "debug_warp":\n                        await self.sim_time_warp(data.get("seconds", 300))\n                    elif msg_type == "workspace_save":',
        "desc": "Expose debug_warp",
    },
]

apply_batch_refinement(target, edits)
