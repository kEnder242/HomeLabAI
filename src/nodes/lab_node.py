#!/usr/bin/env python3
import os
import ctypes
import numpy as np

# --- System Dynamic Linker Workaround ---
try:
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libopenblas.so", mode=ctypes.RTLD_GLOBAL)
except Exception as e:
    print(f"[Warning] Local BLAS pre-load path mismatch: {e}")

from mcp.server.fastmcp import FastMCP, Context
from turbovec import IdMapIndex

mcp = FastMCP("turbovec-mcp")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIMENSION = 768

CURRENT_INDEX = None
DOCUMENT_STORE = {}
CURRENT_INDEX_NAME = None

def get_index_paths(directory_path: str) -> tuple[str, str]:
    """Resolves an explicit, sanitized filename based on the target folder."""
    # Fully expand and resolve symlinks to prevent mismatch variations
    sanitized_path = os.path.realpath(os.path.normpath(directory_path))
    folder_name = os.path.basename(sanitized_path)
    
    if not folder_name:
        folder_name = "default_root_index"
        
    matrix_path = os.path.join(BASE_DIR, f"{folder_name}.tvim")
    meta_path = os.path.join(BASE_DIR, f"{folder_name}.tvim.json")
    return matrix_path, meta_path

def load_index_into_memory(directory_path: str):
    global CURRENT_INDEX, DOCUMENT_STORE, CURRENT_INDEX_NAME
    matrix_path, meta_path = get_index_paths(directory_path)
    
    if CURRENT_INDEX_NAME == matrix_path and CURRENT_INDEX is not None:
        return

    if os.path.exists(matrix_path) and os.path.exists(meta_path):
        try:
            CURRENT_INDEX = IdMapIndex.load(matrix_path)
            import json
            with open(meta_path, "r") as f:
                DOCUMENT_STORE = {int(k): v for k, v in json.load(f).items()}
            CURRENT_INDEX_NAME = matrix_path
        except Exception:
            # Fallback if file corrupts
            CURRENT_INDEX = IdMapIndex(dim=DIMENSION, bit_width=4)
            DOCUMENT_STORE = {}
            CURRENT_INDEX_NAME = matrix_path
    else:
        CURRENT_INDEX = IdMapIndex(dim=DIMENSION, bit_width=4)
        DOCUMENT_STORE = {}
        CURRENT_INDEX_NAME = matrix_path

@mcp.tool()
async def index_directory(directory_path: str, ctx: Context) -> str:
    """Recursively parses technical files, chunking data safely using native async framework vectors."""
    global CURRENT_INDEX, DOCUMENT_STORE
    
    # Resolve exact path semantics
    target_dir = os.path.realpath(os.path.normpath(directory_path))
    if not os.path.isdir(target_dir):
        return f"Error: {target_dir} is not a valid directory."
    
    matrix_path, meta_path = get_index_paths(target_dir)
    load_index_into_memory(target_dir)
    
    target_files = []
    # Explicitly avoid tracking massive hidden cache trees like .git, .venv, node_modules
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '.venv', 'node_modules', '__pycache__')]
        for file in files:
            if file.endswith(('.py', '.json', '.md')):
                target_files.append(os.path.join(root, file))
                
    total_files = len(target_files)
    if total_files == 0:
        return f"No target files (.py, .md, .json) found in {target_dir} after filtering caches."
        
    indexed_chunks = 0
    await ctx.info(f"Targeting File: {os.path.basename(matrix_path)} | Total structural files found: {total_files}")
    
    for index_idx, file_path in enumerate(target_files):
        await ctx.report_progress(progress=index_idx, total=total_files)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            chunks = [content[i:i+1000] for i in range(0, len(content), 800)]
            
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                
                chunk_id = hash(f"{file_path}_{i}") & 0xFFFFFFFFFFFFFFFF
                
                # Use pure native protocol context embeddings (Non-blocking async)
                vector = await ctx.session.create_embedding(text=chunk)
                vector_np = np.array([vector], dtype=np.float32)
                
                CURRENT_INDEX.add_with_ids(vector_np, np.array([chunk_id], dtype=np.uint64))
                
                DOCUMENT_STORE[chunk_id] = {
                    "path": file_path,
                    "text": chunk
                }
                indexed_chunks += 1
        except Exception as e:
            # Explicit diagnostic tracking
            await ctx.error(f"Skipped file {os.path.basename(file_path)} due to error: {str(e)}")
            continue
            
    # Save the states down tightly
    if indexed_chunks > 0:
        CURRENT_INDEX.write(matrix_path)
        import json
        with open(meta_path, "w") as f:
            json.dump(DOCUMENT_STORE, f)
            
    await ctx.report_progress(progress=total_files, total=total_files)
    return f"Successfully saved {indexed_chunks} code segments to {os.path.basename(matrix_path)}."

@mcp.tool()
async def turbovec_search(query: str, directory_path: str, ctx: Context, top_k: int = 3) -> str:
    """Queries a specific project index by pathing target location matching."""
    target_dir = os.path.realpath(os.path.normpath(directory_path))
    matrix_path, _ = get_index_paths(target_dir)
    
    load_index_into_memory(target_dir)
    
    if not DOCUMENT_STORE:
        return f"Index empty for path target target: {os.path.basename(matrix_path)}"
        
    await ctx.info(f"Scanning matrix file: {os.path.basename(matrix_path)} for '{query}'")
    query_vector = await ctx.session.create_embedding(text=query)
    query_np = np.array([query_vector], dtype=np.float32)
    
    scores, ids = CURRENT_INDEX.search(query_np, k=top_k)
    
    output_blocks = []
    for score, vector_id in zip(scores[0], ids[0]):
        v_id = int(vector_id)
        if v_id in DOCUMENT_STORE:
            meta = DOCUMENT_STORE[v_id]
            output_blocks.append(
                f"--- File: {meta['path']} (Distance Score: {score:.4f}) ---\n{meta['text']}\n"
            )
            
    if not output_blocks:
        return "No matches located matching that query string signature."
        
    return "\n".join(output_blocks)

if __name__ == "__main__":
    mcp.run(transport='stdio')