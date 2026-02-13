import sys
import os
from atomic_patcher import apply_batch_refinement

target = "HomeLabAI/src/lab_attendant.py"

edits = [
    {
        "old": 'async with session.get("http://localhost:8088/v1/models", timeout=0.5) as r:',
        "new": 'url = "http://localhost:8088/v1/models"\n                async with session.get(url, timeout=0.5) as r:',
        "desc": "Split long vLLM URL"
    },
    {
        "old": 'if r.status == 200: status["vllm_running"] = True',
        "new": 'if r.status == 200:\n                        status["vllm_running"] = True',
        "desc": "Fix long line in vLLM status"
    },
    {
        "old": "        except: pass",
        "new": "        except Exception:\n            pass",
        "desc": "Fix bare except in vLLM check"
    },
    {
        "old": "                except:\n                    pass",
        "new": "                except Exception:\n                    pass",
        "desc": "Fix bare except in status loop"
    },
    {
        "old": '[LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", data.get("mode", "SERVICE_UNATTENDED")],',
        "new": '[\n                    LAB_VENV_PYTHON, LAB_SERVER_PATH,\n                    "--mode", data.get("mode", "SERVICE_UNATTENDED")\n                ],',
        "desc": "Split long Hub start list"
    },
    {
        "old": 'if data.get("disable_ear", True): env["DISABLE_EAR"] = "1"',
        "new": 'if data.get("disable_ear", True):\n            env["DISABLE_EAR"] = "1"',
        "desc": "Fix multiple statements in EAR disable"
    },
    {
        "old": "with open(SERVER_LOG, 'w') as f: f.write('')",
        "new": "with open(SERVER_LOG, 'w') as f:\n            f.write('')",
        "desc": "Fix multiple statements in log truncate"
    }
]

apply_batch_refinement(target, edits)
