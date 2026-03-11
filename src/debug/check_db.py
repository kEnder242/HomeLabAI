import os, sys, json
sys.path.append(os.path.expanduser("~/Dev_Lab/HomeLabAI/src"))
from nodes.archive_node import stream, wisdom

def inspect_col(col, name):
    res = col.get(limit=2)
    print(f"\n{name} SAMPLE:")
    print(json.dumps(res.get("metadatas"), indent=2))
    
    # Check if any have 'date'
    res_date = col.get(limit=1, where={"date": {"$contains": "20"}})
    print(f"Has date filter results: {len(res_date.get('ids', [])) > 0}")

inspect_col(wisdom, "WISDOM")
inspect_col(stream, "STREAM")
