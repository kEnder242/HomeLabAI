import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 9402

class GPUExporter(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            metrics = self.get_nvidia_metrics()
            self.wfile.write(metrics.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def get_nvidia_metrics(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            used = info.used // 1024 // 1024
            total = info.total // 1024 // 1024
            util = util_info.gpu
            pynvml.nvmlShutdown()
            
            res = [
                "# HELP gpu_memory_used_bytes GPU memory used in MiB",
                "# TYPE gpu_memory_used_bytes gauge",
                f"gpu_memory_used_bytes {used}",
                "# HELP gpu_memory_total_bytes GPU memory total in MiB",
                "# TYPE gpu_memory_total_bytes gauge",
                f"gpu_memory_total_bytes {total}",
                "# HELP gpu_utilization GPU utilization percentage",
                "# TYPE gpu_utilization gauge",
                f"gpu_utilization {util}"
            ]
            return "\n".join(res) + "\n"
        except Exception as e:
            return f"# ERROR: {e}\n"

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    print(f"Silicon-Sentry online on {PORT}")
    server = HTTPServer(("0.0.0.0", PORT), GPUExporter)
    server.serve_forever()
