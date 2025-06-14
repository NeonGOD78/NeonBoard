from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests
import os
import psutil
import shutil

app = Flask(__name__)

# Miljøvariabler
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9861"))
DOWNLOADS_PATH = os.getenv("DOWNLOADS_PATH", "/mnt/local/downloads")

# Prometheus metrics
# --- Tautulli ---
tautulli_active_streams = Gauge('tautulli_active_streams', 'Number of active streams')
tautulli_bandwidth = Gauge('tautulli_bandwidth_total_kbps', 'Total bandwidth usage in kbps')
tautulli_transcodes = Gauge('tautulli_transcodes_active', 'Number of active transcodes')

# --- System metrics ---
cpu_usage = Gauge('system_cpu_usage_percent', 'Current CPU usage in percent')
ram_usage = Gauge('system_ram_usage_percent', 'Current RAM usage in percent')
disk_root_usage = Gauge('system_disk_root_bytes_free', 'Free disk space on / in bytes')
disk_downloads_usage = Gauge('system_disk_downloads_bytes_free', 'Free disk space on downloads mount in bytes')

@app.route("/metrics")
def metrics():
    update_tautulli_metrics()
    update_system_metrics()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def update_tautulli_metrics():
    try:
        response = requests.get(
            f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity",
            timeout=5
        )
        data = response.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])

        active_streams = len(sessions)
        total_bandwidth = sum(int(s.get("wan_bandwidth", 0)) for s in sessions)
        active_transcodes = sum(1 for s in sessions if s.get("transcode_decision") == "transcode")

        tautulli_active_streams.set(active_streams)
        tautulli_bandwidth.set(total_bandwidth)
        tautulli_transcodes.set(active_transcodes)
    except Exception as e:
        print(f"[ERROR] Tautulli metrics failed: {e}")
        tautulli_active_streams.set(0)
        tautulli_bandwidth.set(0)
        tautulli_transcodes.set(0)

def update_system_metrics():
    try:
        cpu_usage.set(psutil.cpu_percent(interval=0.5))
        ram_usage.set(psutil.virtual_memory().percent)

        root_total, root_used, root_free = shutil.disk_usage("/")
        disk_root_usage.set(root_free)

        dl_total, dl_used, dl_free = shutil.disk_usage(DOWNLOADS_PATH)
        disk_downloads_usage.set(dl_free)
    except Exception as e:
        print(f"[ERROR] System metrics failed: {e}")
        disk_root_usage.set(0)
        disk_downloads_usage.set(0)

if __name__ == "__main__":
    print(f"Starting exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
