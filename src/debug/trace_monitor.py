import os
import logging

class TraceMonitor:
    """
    [FEAT-151] Unified Trace Monitoring (Log Delta Capture).
    Marks log positions at start and captures only the NEW lines (deltas) 
    produced during a test window.
    """
    def __init__(self, log_paths):
        self.log_paths = log_paths
        self.marks = {}
        self.refresh_marks()

    def refresh_marks(self):
        """Reset the 'Start' point to the current end of files."""
        for path in self.log_paths:
            if os.path.exists(path):
                self.marks[path] = os.path.getsize(path)
            else:
                self.marks[path] = 0

    def capture_delta(self):
        """Reads and returns only the lines added since the last mark/refresh."""
        deltas = []
        for path in self.log_paths:
            if not os.path.exists(path):
                continue
            
            current_size = os.path.getsize(path)
            mark = self.marks.get(path, 0)
            
            if current_size > mark:
                with open(path, 'r') as f:
                    f.seek(mark)
                    lines = f.readlines()
                    label = os.path.basename(path).upper()
                    for line in lines:
                        deltas.append(f"  [{label}] {line.strip()}")
                
                # Update mark to avoid duplicates if called repeatedly
                self.marks[path] = current_size
        return deltas

    def print_delta(self):
        """Convenience method to immediately print new trace lines."""
        lines = self.capture_delta()
        for line in lines:
            print(line)
        return len(lines) > 0
