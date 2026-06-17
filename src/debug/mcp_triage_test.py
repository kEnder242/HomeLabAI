import asyncio
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

async def run():
    params = StdioServerParameters(command="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3", args=["HomeLabAI/src/nodes/lab_node.py"])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            triage_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "triage_result",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "intent": {"type": "string", "enum": ["STRATEGIC", "CASUAL", "RECALL"]},
                            "addressed_to": {"type": "string", "enum": ["BRAIN", "PINKY", "MICE"]},
                            "vibe": {"type": "string", "enum": ["SILICON_TELEMETRY", "ARCHIVE_HISTORY", "PINKY_INTERFACE"]},
                            "domain": {"type": "string", "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard"]},
                            "casual": {"type": "number"},
                            "intrigue": {"type": "number"},
                            "importance": {"type": "number"},
                            "situation": {"type": "string"},
                            "hints": {"type": "string"}
                        },
                        "required": ["intent", "addressed_to", "vibe", "domain"]
                    }
                }
            }
            
            res = await session.call_tool("think", {
                "query": "[ME] Status of the lab?",
                "response_format": triage_schema,
                "internal": False
            })
            print("RESULT:", res)

if __name__ == "__main__":
    asyncio.run(run())
