import psutil
import json
import os

def get_hog_report():
    print("=== 🐗 SYSTEM HOG REPORT (Non-Lab Context) ===")
    
    # 1. Total System Vitals
    mem = psutil.virtual_memory()
    print(f"System RAM: {mem.used / (1024**3):.2f} GiB / {mem.total / (1024**3):.2f} GiB ({mem.percent}%)")
    
    # 2. Identify Non-Lab Hogs
    # Improved signatures: capture nodes regardless of session ID suffix
    lab_signatures = ['vllm', 'ollama', 'acme_lab', 'thinking_node', 'pinky_node', 'brain_node', 'shadow_node', 'archive_node', 'lab_node', 'browser_node', 'lab_attendant']
    
    hogs = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'username']):
        try:
            cmd = " ".join(proc.info['cmdline'] or []).lower()
            # Catch nodes by name or cmdline
            is_lab = any(sig in cmd for sig in lab_signatures) or any(sig in proc.info['name'].lower() for sig in lab_signatures)
            
            if not is_lab and proc.info['username'] == psutil.Process().username():
                mem_mib = proc.info['memory_info'].rss / (1024 * 1024)
                if mem_mib > 50: # Report processes > 50 MiB
                    hogs.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "mem_mib": mem_mib,
                        "cmd": cmd[:150]
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    hogs.sort(key=lambda x: x['mem_mib'], reverse=True)
    
    print(f"\nTop Non-Lab Memory Hogs (>50MiB):")
    for h in hogs[:15]:
        print(f"  - [{h['name']}] (PID {h['pid']}): {h['mem_mib']:.1f} MiB")
        print(f"    CMD: {h['cmd']}")
    
    # 3. Contextual Audits
    vscode_total = sum(h['mem_mib'] for h in hogs if 'vscode' in h['cmd'] or 'code-server' in h['cmd'] or '.vscode-server' in h['cmd'])
    gemini_total = sum(h['mem_mib'] for h in hogs if 'gemini' in h['cmd'] or 'node' in h['cmd'] and 'bin/gemini' in h['cmd'])
    
    print(f"\nContextual Totals:")
    print(f"  - VS Code (Server/Ext): {vscode_total:.1f} MiB")
    print(f"  - Gemini CLI (Self): {gemini_total:.1f} MiB")
    print(f"  - Steam / Graphics: {sum(h['mem_mib'] for h in hogs if 'steam' in h['cmd'] or 'gnome' in h['cmd']):.1f} MiB")

if __name__ == "__main__":
    get_hog_report()
