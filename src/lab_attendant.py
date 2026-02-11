import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import os
import subprocess
import signal
import psutil # For graceful process management
import sys 
import argparse
import datetime # ADDED THIS

# --- Configuration ---
LAB_PORT = 8765
ATTENDANT_PORT = 9999
LAB_SERVER_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/acme_lab.py")
LAB_DIR = os.path.dirname(os.path.dirname(LAB_SERVER_PATH)) # Corrected: Go up two levels from acme_lab.py to HomeLabAI
LAB_VENV_PYTHON = os.path.join(LAB_DIR, ".venv", "bin", "python3")
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
ROUND_TABLE_LOCK = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table.lock")

# --- Logger Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ATTENDANT] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# --- Global State ---
lab_process: subprocess.Popen = None
current_lab_mode: str = "OFFLINE"
last_logged_lab_pid: int = None
last_logged_lab_ready_state: bool = False
last_logged_lab_status_message: str = ""

class LabAttendant:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_get("/status", self.handle_status)
        self.app.router.add_post("/start", self.handle_start)
        self.app.router.add_post("/stop", self.handle_stop)
        self.app.router.add_post("/cleanup", self.handle_cleanup)
        self.app.router.add_get("/logs", self.handle_logs)

    async def handle_status(self, request):
        status = await self._get_lab_status()
        
        # Enhanced logging to Attendant's journal
        global last_logged_lab_pid, last_logged_lab_ready_state, last_logged_lab_status_message
        
        if status["lab_pid"] != last_logged_lab_pid:
            if status["lab_pid"]:
                logger.info(f"acme_lab.py PID changed: {last_logged_lab_pid} -> {status['lab_pid']}")
            else:
                logger.info(f"acme_lab.py PID {last_logged_lab_pid} terminated.")
            last_logged_lab_pid = status["lab_pid"]

        if status["full_lab_ready"] != last_logged_lab_ready_state:
            logger.info(f"acme_lab.py READY state changed: {last_logged_lab_ready_state} -> {status['full_lab_ready']}")
            last_logged_lab_ready_state = status["full_lab_ready"]
        
        if status["lab_server_running"] and status["last_log_lines"]:
            latest_lab_status_line = next((line for line in reversed(status["last_log_lines"]) if "[LAB] INFO -" in line), None)
            if latest_lab_status_line and latest_lab_status_line != last_logged_lab_status_message:
                logger.info(f"acme_lab.py latest status: {latest_lab_status_line.split(' - ', 2)[-1]}")
                last_logged_lab_status_message = latest_lab_status_line

        return web.json_response(status)

    async def handle_start(self, request):
        global lab_process, current_lab_mode, last_logged_lab_pid, last_logged_lab_ready_state, last_logged_lab_status_message
        if lab_process and lab_process.poll() is None:
            return web.json_response({"status": "error", "message": "Lab server already running."}, status=409)

        data = await request.json()
        mode = data.get("mode", "SERVICE_UNATTENDED")
        
        # Merge provided env vars with existing ones
        process_env = os.environ.copy() # CORRECTED: Use process_env instead of env
        process_env.update(data.get("env", {})) # Pass additional env vars

        

        process_env["PYTHONPATH"] = f"{process_env.get('PYTHONPATH', '')}:{LAB_DIR}/src"

        process_env["PYTHONUNBUFFERED"] = "1"

        process_env["CUDA_LAUNCH_BLOCKING"] = "1" # ADDED: Force Eager Mode for PyTorch/Nemo

        # Handle DISABLE_EAR specifically, as it's a common control
        if data.get("disable_ear", True): # Default to disabled if not specified
            process_env["DISABLE_EAR"] = "1"
        else:
            process_env.pop("DISABLE_EAR", None) # Ensure it's not set if enabling
        
        # Explicit Engine Selection
        if "PINKY_ENGINE" in os.environ:
            process_env["PINKY_ENGINE"] = os.environ["PINKY_ENGINE"]
        
        logger.info(f"Starting Lab server in mode: {mode}, ear: {not data.get('disable_ear', True)}, engine: {process_env.get('PINKY_ENGINE', 'AUTO')}")

        # Ensure SERVER_LOG exists and is empty for a clean run
        with open(SERVER_LOG, 'w') as f: f.write('')

        try:
            # Launch acme_lab.py and redirect its stderr to SERVER_LOG
            lab_process = subprocess.Popen(
                [LAB_VENV_PYTHON, LAB_SERVER_PATH, "--mode", mode],
                cwd=LAB_DIR, 
                env=process_env, # CORRECTED: Use process_env here
                stdout=subprocess.DEVNULL, # acme_lab.py only logs to stderr now
                stderr=open(SERVER_LOG, 'a', buffering=1) # Redirect stderr to SERVER_LOG, line-buffered
            )
            current_lab_mode = mode
            last_logged_lab_pid = lab_process.pid
            last_logged_lab_ready_state = False # Reset on new start
            last_logged_lab_status_message = "" # Reset on new start
            logger.info(f"Lab server launched with PID: {lab_process.pid}")
            return web.json_response({"status": "success", "message": "Lab server started.", "pid": lab_process.pid})
        except Exception as e:
            logger.error(f"Failed to start Lab server: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_stop(self, request):
        global lab_process, current_lab_mode, last_logged_lab_pid, last_logged_lab_ready_state, last_logged_lab_status_message
        if lab_process and lab_process.poll() is None:
            logger.info(f"Stopping Lab server with PID: {lab_process.pid}")
            try:
                # Use psutil for graceful shutdown
                parent = psutil.Process(lab_process.pid)
                for child in parent.children(recursive=True):
                    child.send_signal(signal.SIGTERM)
                parent.send_signal(signal.SIGTERM)
                
                # Wait for process to terminate
                try:
                    lab_process.wait(timeout=10) # Wait up to 10 seconds
                except subprocess.TimeoutExpired:
                    logger.warning(f"Lab process {lab_process.pid} did not terminate gracefully, sending SIGKILL.")
                    lab_process.kill()
                    lab_process.wait()
                
                lab_process = None
                current_lab_mode = "OFFLINE"
                last_logged_lab_pid = None # Reset
                last_logged_lab_ready_state = False # Reset
                last_logged_lab_status_message = "" # Reset
                logger.info("Lab server stopped.")
                return web.json_response({"status": "success", "message": "Lab server stopped."})
            except psutil.NoSuchProcess:
                logger.warning("Lab process not found, likely already terminated.")
                lab_process = None
                current_lab_mode = "OFFLINE"
                last_logged_lab_pid = None # Reset
                last_logged_lab_ready_state = False # Reset
                last_logged_lab_status_message = "" # Reset
                return web.json_response({"status": "success", "message": "Lab process not found, assumed stopped."})
            except Exception as e:
                logger.error(f"Error stopping Lab server: {e}")
                return web.json_response({"status": "error", "message": str(e)}, status=500)
        else:
            return web.json_response({"status": "info", "message": "Lab server not running."})

    async def handle_cleanup(self, request):
        global lab_process
        if lab_process and lab_process.poll() is None:
            return web.json_response({"status": "error", "message": "Cannot cleanup while Lab server is running. Please stop it first."}, status=400)
        
        logger.info("Performing cleanup...")
        try:
            if os.path.exists(SERVER_LOG):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_path = f"{SERVER_LOG}.{timestamp}"
                os.rename(SERVER_LOG, archive_path)
                logger.info(f"Archived {SERVER_LOG} to {archive_path}")
            else:
                logger.info(f"{SERVER_LOG} not found, no archive needed.")
            
            if os.path.exists(ROUND_TABLE_LOCK):
                os.remove(ROUND_TABLE_LOCK)
                logger.info(f"Removed {ROUND_TABLE_LOCK}")
            else:
                logger.info(f"{ROUND_TABLE_LOCK} not found.")

            return web.json_response({"status": "success", "message": "Cleanup complete."})
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_logs(self, request):
        try:
            if os.path.exists(SERVER_LOG):
                with open(SERVER_LOG, 'r') as f:
                    logs = f.read()
                return web.Response(text=logs, content_type='text/plain')
            else:
                return web.json_response({"status": "info", "message": "server.log not found."}, status=404)
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _get_lab_status(self):
        status = {
            "attendant_pid": os.getpid(),
            "lab_server_running": False,
            "lab_pid": None,
            "lab_mode": current_lab_mode,
            "lab_port_listening": False,
            "round_table_lock_exists": os.path.exists(ROUND_TABLE_LOCK),
            "last_log_lines": [],
            "vram_usage": "UNKNOWN",
            "full_lab_ready": False # Based on log parsing
        }

        if lab_process and lab_process.poll() is None: # Check if acme_lab process is alive
            status["lab_server_running"] = True
            status["lab_pid"] = lab_process.pid
            
            # Check port 8765
            try:
                # Use netstat/lsof to check if port is truly listening
                output = subprocess.check_output(["sudo", "lsof", "-i", f":{LAB_PORT}"]).decode()
                if str(LAB_PORT) in output:
                    status["lab_port_listening"] = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Get last log lines
            try:
                if os.path.exists(SERVER_LOG):
                    with open(SERVER_LOG, 'r') as f:
                        lines = f.readlines()
                        status["last_log_lines"] = [line.strip() for line in lines[-10:]]
                        # Check for READY signal in logs
                        if any("[READY] Lab is Open" in line for line in lines):
                            status["full_lab_ready"] = True
            except Exception as e:
                logger.warning(f"Error reading server log: {e}")

            # Get VRAM usage
            try:
                output = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).decode().strip()
                status["vram_usage"] = f"{output}MiB"
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

        return status

    async def run(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', ATTENDANT_PORT)
        logger.info(f"Lab Attendant starting on port {ATTENDANT_PORT}")
        await site.start()
        logger.info("Lab Attendant ready.")
        await asyncio.Event().wait() # Keep running until interrupted

async def main():
    parser = argparse.ArgumentParser(description="Lab Attendant Orchestrator")
    parser.add_argument("--run-once", action="store_true", help="Run status check once and exit.")
    args = parser.parse_args()

    attendant = LabAttendant()
    if args.run_once:
        logger.info("Running Lab Attendant in --run-once mode.")
        status = await attendant._get_lab_status()
        logger.info(json.dumps(status, indent=2))
    else:
        await attendant.run()

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        logger.error("psutil not found. Please install with: pip install psutil")
        sys.exit(1)
    
    asyncio.run(main())