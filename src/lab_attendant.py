import os
import logging
import asyncio
import subprocess
import time
from aiohttp import web

# Resolve repo root for git operations
_REPO_ROOT = None
def get_repo_root():
    """Return absolute path to repository root, caching result."""
    global _REPO_ROOT
    if _REPO_ROOT is None:
        current = os.path.abspath(__file__)
        while not os.path.exists(os.path.join(current, '.git')):
            parent = os.path.dirname(current)
            if parent == current:
                _REPO_ROOT = os.path.dirname(current)
                break
            current = parent
        else:
            _REPO_ROOT = current
    return _REPO_ROOT

def get_boot_commit() -> str:
    """Get short git commit hash (7 chars), fallback to 'unknown'."""
    try:
        root = get_repo_root()
        result = subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'],
                               capture_output=True, text=True, cwd=root)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"

def get_boot_timestamp() -> int:
    """Get boot timestamp as epoch integer."""
    return int(time.time())

async def version_handler(request):
    """GET /version endpoint returning boot metadata."""
    commit = get_boot_commit()
    timestamp = get_boot_timestamp()
    payload = {
        "boot_commit": commit,
        "boot_timestamp": timestamp,
        "service": "lab-attendant"
    }
    return web.json_response(payload)

app = web.Application()
app.add_routes([
    web.get('/version', version_handler),
])

async def cleanup(app):
    """Cleanup on shutdown."""
    logging.info("Lab Attendant shutting down")

app.on_cleanup.append(cleanup)

async def start_server(host: str = "0.0.0.0", port: int = 8765) -> web.AppRunner:
    """Start aiohttp server with graceful shutdown support."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logging.info(f"Lab Attendant started on {host}:{port}")
    return runner

async def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO)
    runner = await start_server()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutdown requested")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
