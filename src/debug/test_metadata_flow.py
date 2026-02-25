import asyncio
import json
import websockets


async def test_metadata_flow():
    print("--- [DIAGNOSTIC] Metadata & Transparency Flow ---")

    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await asyncio.sleep(2)

            # This query SHOULD trigger the 2010 year-scanner and return 2010.json as a source
            query = "Analyze my work in 2010."
            print(f"Sending: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))

            for _ in range(15):
                msg = await websocket.recv()
                data = json.loads(msg)

                # We are looking for the 'sources' and 'oracle_category' fields in the broadcast
                if "brain" in data:
                    src = data.get("brain_source", "Unknown")
                    sources = data.get("sources", [])
                    oracle = data.get("oracle_category", "None")

                    print(f"[{src}] Oracle: {oracle} | Sources: {sources}")

                    if src == "Brain (Signal)" and oracle == "RETRIEVING":
                        print("✅ Oracle State detected in broadcast.")

                    if src == "Brain" and len(sources) > 0:
                        print(
                            f"✅ Metadata Transparency Verified. Sources found: {sources}"
                        )
                        return True

                await asyncio.sleep(0.5)

        print("❌ FAILED: No metadata (sources/oracle) found in live broadcast.")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_metadata_flow())
