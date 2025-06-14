from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests
import os
import psutil
import shutil
import platform
import time
import subprocess

app = Flask(__name__)

# ========== Miljøvariabler ==========
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
QBIT_URL = os.getenv("QBIT_URL", "http://localhost:8080")
QBIT_USER = os.getenv("QBIT_USER")
QBIT_PASS = os.getenv("QBIT_PASS")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9814"))

# ========== Prometheus metrics ==========
# Tautulli
tautulli_active_streams = Gauge("tautulli_active_streams", "Number of active streams")
tautulli_bandwidth_total = Gauge("tautulli_bandwidth_total_kbps", "Total bandwidth usage in kbps")
tautulli_transcodes_active = Gauge("tautulli_transcodes_active", "Number of active transcodes")

# System
cpu_usage = Gauge("neonboard_cpu_usage_percent", "Current CPU usage in percent")
ram_usage = Gauge("neonboard_ram_usage_percent", "Current RAM usage in percent")
disk_root_free = Gauge("neonboard_disk_root_bytes_free", "Free disk space on / in bytes")
disk_downloads_free = Gauge("neonboard_disk_downloads_bytes_free", "Free disk space on downloads mount in bytes")
uptime = Gauge("neonboard_uptime_seconds", "System uptime in seconds")
cpu_base_clock = Gauge("neonboard_cpu_base_clock_ghz", "Base clock speed of CPU in GHz")
cpu_cores = Gauge("neonboard_cpu_cores_total", "Total number of logical CPU cores")
cpu_threads = Gauge("neonboard_cpu_threads_total", "Total number of threads (logical)")
cpu_sockets = Gauge("neonboard_cpu_sockets_total", "Number of physical sockets")

# Top processes
top_cpu_process = Gauge("neonboard_top_cpu_process_percent", "Top process by CPU usage", ["pid", "name"])
top_ram_process = Gauge("neonboard_top_ram_process_bytes", "Top process by RAM usage", ["pid", "name"])

@app.route("/metrics")
def metrics():
    try:
        # ===== Tautulli =====
        tautulli_res = requests.get(
            f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity",
            timeout=5
        )
        tautulli_data = tautulli_res.json()
        sessions = tautulli_data.get("response", {}).get("data", {}).get("sessions", [])

        tautulli_active_streams.set(len(sessions))
        total_bandwidth = sum(int(s.get("wan_bandwidth", 0)) for s in sessions)
        tautulli_bandwidth_total.set(total_bandwidth)
        tautulli_transcodes_active.set(sum(1 for s in sessions if s.get("transcode_decision") == "transcode"))

        # ===== System metrics =====
        cpu_usage.set(psutil.cpu_percent())
        ram_usage.set(psutil.virtual_memory().percent)
        uptime.set(time.time() - psutil.boot_time())

        disk_root = shutil.disk_usage("/")
        disk_root_free.set(disk_root.free)

        try:
            qbit_res = requests.get(f"{QBIT_URL}/api/v2/auth/login", auth=(QBIT_USER, QBIT_PASS), timeout=5)
            if qbit_res.ok:
                downloads_mount = "/mnt/local/downloads"
                if os.path.exists(downloads_mount):
                    downloads_stat = shutil.disk_usage(downloads_mount)
                    disk_downloads_free.set(downloads_stat.free)
        except Exception as e:
            print(f"[WARN] Failed to get qBittorrent download path: {e}")

        # ===== CPU info =====
        cpu_cores.set(psutil.cpu_count(logical=True))
        cpu_threads.set(psutil.cpu_count(logical=True))
        cpu_sockets.set(len(psutil.cpu_stats()))

        try:
            # base clock via /proc/cpuinfo or lscpu
            lscpu = subprocess.run(["lscpu"], capture_output=True, text=True)
            for line in lscpu.stdout.splitlines():
                if "CPU MHz" in line:
                    mhz = float(line.split(":")[1].strip())
                    cpu_base_clock.set(round(mhz / 1000, 2))
                    break
        except Exception as e:
            print(f"[WARN] Could not determine base clock: {e}")

        # ===== Top processes =====
        processes = [(p.info["pid"], p.info["name"], p.info["cpu_percent"], p.info["memory_info"].rss)
                     for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"])]

        top_by_cpu = sorted(processes, key=lambda p: p[2], reverse=True)[:5]
        top_by_ram = sorted(processes, key=lambda p: p[3], reverse=True)[:5]

        for pid, name, cpu, _ in top_by_cpu:
            top_cpu_process.labels(pid=str(pid), name=name).set(cpu)

        for pid, name, _, ram in top_by_ram:
            top_ram_process.labels(pid=str(pid), name=name).set(ram)

    except Exception as e:
        print(f"[ERROR] Exporter failed: {e}")

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    print(f"Starting NeonBoard Exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
