import psutil
import json
import os

def get_hog_report():
    print("=== 🐗 SYSTEM RESOURCE BALANCE SHEET ===")
    
    # 1. Total System Vitals
    mem = psutil.virtual_memory()
    total_used_mib = mem.used / (1024 * 1024)
    print(f"Total Used RAM: {total_used_mib / 1024:.2f} GiB / {mem.total / (1024**3):.2f} GiB ({mem.percent}%)")
    
    # 2. Categories
    lab_sigs = ['vllm', 'ollama', 'acme_lab', 'thinking_node', 'pinky_node', 'brain_node', 'shadow_node', 'archive_node', 'lab_node', 'browser_node', 'lab_attendant', 'python3']
    user_sigs = ['steam', 'jellyfin', 'gnome', 'chrome', 'firefox', 'vscode', 'code-server', '.vscode-server', 'sunshine', 'gemini', 'bun', 'node']
    docker_sigs = ['prometheus', 'grafana', 'loki', 'dcgm-exporter']
    
    summary = {
        "Lab Controlled": 0.0,
        "User/Tools": 0.0,
        "Observability (Docker)": 0.0,
        "System/Root/Kernel": 0.0
    }
    
    detailed_hogs = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'username']):
        try:
            pinfo = proc.info
            cmd = " ".join(pinfo['cmdline'] or "").lower()
            name = (pinfo['name'] or "").lower()
            rss = pinfo['memory_info'].rss / (1024 * 1024)
            
            # Refined Lab Check: Catch bracketed nodes like [ARCHIVE:...]
            is_lab = any(s.lower() in cmd or s.lower() in name for s in lab_sigs)
            if not is_lab and (("[" in cmd and ":" in cmd) or ("[" in name and ":" in name)):
                # High probability of being a lab node fingerprint
                is_lab = True
                
            is_user = any(s.lower() in cmd or s.lower() in name for s in user_sigs)
            is_docker = any(s.lower() in cmd or s.lower() in name for s in docker_sigs)
            
            if is_lab:
                summary["Lab Controlled"] += rss
            elif is_docker:
                summary["Observability (Docker)"] += rss
            elif is_user:
                summary["User/Tools"] += rss
            else:
                summary["System/Root/Kernel"] += rss
                
            if rss > 100:
                detailed_hogs.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "rss": rss,
                    "cat": "LAB" if is_lab else "DOCKER" if is_docker else "USER" if is_user else "SYS"
                })
        except: continue

    # 3. Output Table
    print(f"\n{'Category':<25} | {'Memory (MiB)':<12} | {'% of Used':<8}")
    print("-" * 55)
    for cat, val in summary.items():
        pct = (val / total_used_mib) * 100 if total_used_mib > 0 else 0
        print(f"{cat:<25} | {val:>12.1f} | {pct:>7.1f}%")
    
    print(f"\nTop Consumers (>100MiB):")
    detailed_hogs.sort(key=lambda x: x['rss'], reverse=True)
    for h in detailed_hogs[:15]:
        print(f"  - [{h['cat']}] {h['name']} (PID {h['pid']}): {h['rss']:.1f} MiB")

if __name__ == "__main__":
    get_hog_report()
