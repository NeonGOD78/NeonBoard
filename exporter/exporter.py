from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests
import os
import psutil
import shutil
import time
import platform

app = Flask(__name__)

# ================== Miljøvariabler ==================
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")

QBIT_URL = os.getenv("QBIT_URL", "http://localhost:8080")
QBIT_USER = os.getenv("QBIT_USER", "admin")
QBIT_PASS = os.getenv("QBIT_PASS", "adminadmin")

EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9861"))

# ================== Prometheus Metrics ==================
tautulli_active_streams = Gauge("tautulli_active_streams", "Number of active Tautulli streams")
tautulli_bandwidth = Gauge("tautulli_bandwidth_kbps", "Total bandwidth usage in kbps")
tautulli_transcodes = Gauge("tautulli_transcodes_active", "Number of active transcodes")

cpu_usage = Gauge("neon_cpu_usage_percent", "CPU usage in percent")
cpu_base_freq = Gauge("neon_cpu_base_freq_mhz", "CPU base frequency in MHz")
cpu_current_freq = Gauge("neon_cpu_current_freq_mhz", "Current average CPU frequency in MHz")
cpu_threads = Gauge("neon_cpu_threads", "Total number of threads")
cpu_cores = Gauge("neon_cpu_cores", "Total number of physical cores")
cpu_sockets = Gauge("neon_cpu_sockets", "Number of physical sockets")
uptime_seconds = Gauge("neon_system_uptime_seconds", "System uptime in seconds")

ram_total = Gauge("neon_ram_total_mb", "Total system memory in MB")
ram_used = Gauge("neon_ram_used_mb", "Used system memory in MB")
ram_percent = Gauge("neon_ram_used_percent", "RAM usage in percent")

root_total = Gauge("neon_disk_root_total_gb", "Root partition total size in GB")
root_used = Gauge("neon_disk_root_used_gb", "Root partition used size in GB")
root_percent = Gauge("neon_disk_root_used_percent", "Root partition usage in percent")

downloads_total = Gauge("neon_disk_downloads_total_gb", "Downloads directory total size in GB")
downloads_used = Gauge("neon_disk_downloads_used_gb", "Downloads directory used size in GB")
downloads_percent = Gauge("neon_disk_downloads_used_percent", "Downloads directory usage in percent")

top_cpu = Gauge("neon_top_cpu_process_percent", "Top CPU processes", ["pid", "name"])
top_ram = Gauge("neon_top_ram_process_mb", "Top RAM processes", ["pid", "name"])

# ================== Hjælpefunktioner ==================

def get_uptime():
    return time.time() - psutil.boot_time()

def get_downloads_path():
    try:
        session = requests.Session()
        # Login
        r = session.post(f"{QBIT_URL}/api/v2/auth/login", data={"username": QBIT_USER, "password": QBIT_PASS}, timeout=5)
        if r.text != "Ok":
            raise Exception("Login failed")
        # Get preferences
        prefs = session.get(f"{QBIT_URL}/api/v2/app/preferences", timeout=5)
        return prefs.json().get("save_path", "/mnt/local/downloads")
    except Exception as e:
        print(f"[ERROR] Could not fetch qBittorrent save_path: {e}")
        return "/mnt/local/downloads"

def get_disk_usage(path):
    try:
        usage = shutil.disk_usage(path)
        total = usage.total / (1024 ** 3)
        used = (usage.total - usage.free) / (1024 ** 3)
        percent = used / total * 100
        return total, used, percent
    except Exception as e:
        print(f"[ERROR] Failed disk usage for {path}: {e}")
        return 0, 0, 0

def collect_top_processes():
    procs = [(p.info["pid"], p.info["name"], p.info["cpu_percent"], p.info["memory_info"].rss / (1024 * 1024))
             for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"])]
    # Sort and get top 5
    top_cpu_procs = sorted(procs, key=lambda x: x[2], reverse=True)[:5]
    top_ram_procs = sorted(procs, key=lambda x: x[3], reverse=True)[:5]

    for pid, name, cpu, _ in top_cpu_procs:
        top_cpu.labels(pid=str(pid), name=name).set(cpu)

    for pid, name, _, ram in top_ram_procs:
        top_ram.labels(pid=str(pid), name=name).set(ram)

# ================== /metrics Route ==================

@app.route("/metrics")
def metrics():
    # Tautulli
    try:
        r = requests.get(f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity", timeout=5)
        data = r.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])
        tautulli_active_streams.set(len(sessions))
        tautulli_transcodes.set(sum(1 for s in sessions if s.get("transcode_decision") == "transcode"))
        tautulli_bandwidth.set(sum(int(s.get("wan_bandwidth", 0)) for s in sessions))
    except Exception as e:
        print(f"[ERROR] Tautulli metrics failed: {e}")

    # System info
    cpu_usage.set(psutil.cpu_percent(interval=1))
    freq = psutil.cpu_freq()
    if freq:
        cpu_base_freq.set(freq.min)
        cpu_current_freq.set(freq.current)
    cpu_threads.set(psutil.cpu_count(logical=True))
    cpu_cores.set(psutil.cpu_count(logical=False))
    cpu_sockets.set(len(set(cpu.info.get("cpu", 0) for cpu in psutil.cpu_stats())))
    uptime_seconds.set(get_uptime())

    vm = psutil.virtual_memory()
    ram_total.set(vm.total / (1024 ** 2))
    ram_used.set(vm.used / (1024 ** 2))
    ram_percent.set(vm.percent)

    # Disk info
    root_t, root_u, root_p = get_disk_usage("/")
    root_total.set(root_t)
    root_used.set(root_u)
    root_percent.set(root_p)

    downloads_path = get_downloads_path()
    dl_t, dl_u, dl_p = get_disk_usage(downloads_path)
    downloads_total.set(dl_t)
    downloads_used.set(dl_u)
    downloads_percent.set(dl_p)

    collect_top_processes()

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# ================== Run ==================
if __name__ == "__main__":
    print(f"Starting NeonBoard Exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
