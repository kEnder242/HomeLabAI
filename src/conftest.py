import pytest
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client # Import stdio_client
import sys
import os

# Assuming Python executable path
PYTHON_PATH = sys.executable

@pytest.fixture(scope="session")
def event_loop():
    """Create a session scoped event loop for pytest-asyncio."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def archive_client():
    """
    Starts the archive_node.py as a subprocess and provides an MCP ClientSession.
    """
    server_script = os.path.join(os.path.dirname(__file__), "nodes", "archive_node.py")
    server_params = StdioServerParameters(command=PYTHON_PATH, args=[server_script])
    
    # Correctly use stdio_client context manager to get read/write pipes
    async with stdio_client(server_params) as (read_pipe, write_pipe):
        async with ClientSession(read_pipe, write_pipe) as session:
            # Apply a timeout using asyncio.wait_for for initialization
            await asyncio.wait_for(session.initialize(), timeout=60) # Increased to 60 seconds
            yield session

@pytest.fixture(scope="module")
async def brain_client():
    """
    Starts the brain_node.py as a subprocess and provides an MCP ClientSession.
    """
    server_script = os.path.join(os.path.dirname(__file__), "nodes", "brain_node.py")
    server_params = StdioServerParameters(command=PYTHON_PATH, args=[server_script])
    
    async with stdio_client(server_params) as (read_pipe, write_pipe):
        async with ClientSession(read_pipe, write_pipe) as session:
            # Apply a timeout using asyncio.wait_for for initialization
            await asyncio.wait_for(session.initialize(), timeout=60) # Increased to 60 seconds
            yield session

@pytest.fixture(scope="module")
async def brain_client():
    """
    Starts the brain_node.py as a subprocess and provides an MCP ClientSession.
    """
    server_script = os.path.join(os.path.dirname(__file__), "nodes", "brain_node.py")
    server_params = StdioServerParameters(command=PYTHON_PATH, args=[server_script])
    
    async with stdio_client(server_params) as (read_pipe, write_pipe):
        async with ClientSession(read_pipe, write_pipe) as session:
            await session.initialize()
            yield session
