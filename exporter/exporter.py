from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import psutil
import shutil
import platform
import time
import os
import requests
import json

app = Flask(__name__)

# Miljøvariabler
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9814"))
QBIT_URL = os.getenv("QBIT_URL")
QBIT_USER = os.getenv("QBIT_USER")
QBIT_PASS = os.getenv("QBIT_PASS")

# Prometheus metrics
gauges = {
    "tautulli_active_streams": Gauge("tautulli_active_streams", "Number of active streams"),
    "tautulli_bandwidth_total_kbps": Gauge("tautulli_bandwidth_total_kbps", "Total bandwidth usage in kbps"),
    "tautulli_transcodes_active": Gauge("tautulli_transcodes_active", "Number of active transcodes"),
    "neonboard_cpu_usage_percent": Gauge("neonboard_cpu_usage_percent", "Current CPU usage in percent"),
    "neonboard_ram_usage_percent": Gauge("neonboard_ram_usage_percent", "Current RAM usage in percent"),
    "neonboard_disk_root_bytes_free": Gauge("neonboard_disk_root_bytes_free", "Free disk space on / in bytes"),
    "neonboard_disk_downloads_bytes_free": Gauge("neonboard_disk_downloads_bytes_free", "Free disk space on downloads mount in bytes"),
    "neonboard_uptime_seconds": Gauge("neonboard_uptime_seconds", "System uptime in seconds"),
    "neonboard_cpu_base_mhz": Gauge("neonboard_cpu_base_mhz", "CPU base clock speed in MHz"),
    "neonboard_cpu_sockets": Gauge("neonboard_cpu_sockets", "Number of physical CPU sockets"),
    "neonboard_cpu_cores": Gauge("neonboard_cpu_cores", "Number of physical CPU cores"),
    "neonboard_cpu_threads": Gauge("neonboard_cpu_threads", "Number of logical CPU threads"),
}

top_cpu = Gauge("neonboard_top_cpu_process_percent", "Top process CPU usage", ["name", "pid"])
top_ram = Gauge("neonboard_top_ram_process_mb", "Top process RAM usage in MB", ["name", "pid"])

def get_qbit_download_mount_path():
    try:
        session = requests.Session()
        session.post(f"{QBIT_URL}/api/v2/auth/login", data={
            "username": QBIT_USER,
            "password": QBIT_PASS
        }, timeout=5)

        r = session.get(f"{QBIT_URL}/api/v2/app/preferences", timeout=5)
        data = r.json()
        save_path = data.get("save_path", "")

        # Mulige bind mounts i containeren
        possible_mounts = [
            "/mnt/local/downloads",
            "/downloads",
            "/mnt/qbit-downloads",
        ]

        for mount in possible_mounts:
            if save_path.startswith(mount):
                return mount

        print(f"[WARNING] No matching bind-mount found for save_path: {save_path}")
        return None

    except Exception as e:
        print(f"[WARNING] Failed to get qBittorrent download path: {e}")
        return None

@app.route("/metrics")
def metrics():
    # ================== Tautulli ==================
    try:
        r = requests.get(f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity", timeout=5)
        data = r.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])

        gauges["tautulli_active_streams"].set(len(sessions))
        gauges["tautulli_bandwidth_total_kbps"].set(sum(int(s.get("wan_bandwidth", 0)) for s in sessions))
        gauges["tautulli_transcodes_active"].set(sum(1 for s in sessions if s.get("transcode_decision") == "transcode"))
    except Exception as e:
        print(f"[WARNING] Failed to fetch Tautulli metrics: {e}")

    # ================== System ==================
    try:
        gauges["neonboard_cpu_usage_percent"].set(psutil.cpu_percent(interval=1))
        gauges["neonboard_ram_usage_percent"].set(psutil.virtual_memory().percent)
        gauges["neonboard_uptime_seconds"].set(time.time() - psutil.boot_time())

        freq = psutil.cpu_freq()
        if freq:
            gauges["neonboard_cpu_base_mhz"].set(freq.min)
        gauges["neonboard_cpu_sockets"].set(len(psutil.cpu_stats()))
        gauges["neonboard_cpu_cores"].set(psutil.cpu_count(logical=False))
        gauges["neonboard_cpu_threads"].set(psutil.cpu_count(logical=True))

        root_free = shutil.disk_usage("/").free
        gauges["neonboard_disk_root_bytes_free"].set(root_free)

        downloads_mount = get_qbit_download_mount_path()
        if downloads_mount and os.path.exists(downloads_mount):
            try:
                downloads_free = shutil.disk_usage(downloads_mount).free
            except Exception:
                downloads_free = 0
        else:
            downloads_free = 0
        gauges["neonboard_disk_downloads_bytes_free"].set(downloads_free)

        # Top 5 CPU og RAM processer
        processes = [(p.info["name"], p.pid, p.info["cpu_percent"], p.info["memory_info"].rss / 1024 / 1024)
                     for p in psutil.process_iter(["name", "cpu_percent", "memory_info"])]

        for name, pid, cpu, mem in sorted(processes, key=lambda x: x[2], reverse=True)[:5]:
            top_cpu.labels(name=name, pid=str(pid)).set(cpu)
        for name, pid, cpu, mem in sorted(processes, key=lambda x: x[3], reverse=True)[:5]:
            top_ram.labels(name=name, pid=str(pid)).set(mem)

    except Exception as e:
        print(f"[ERROR] System metrics failed: {e}")

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    print(f"Starting NeonBoard Exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
