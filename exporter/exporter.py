from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests
import os
import psutil
import shutil
import time
import platform
import subprocess

app = Flask(__name__)

# Miljøvariabler
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
QBITTORRENT_URL = os.getenv("QBITTORRENT_URL", "http://localhost:8080")
QBITTORRENT_USERNAME = os.getenv("QBITTORRENT_USERNAME", "admin")
QBITTORRENT_PASSWORD = os.getenv("QBITTORRENT_PASSWORD", "adminadmin")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9861"))

# Prometheus metrics
# Tautulli
tautulli_streams = Gauge('neonboard_tautulli_active_streams', 'Number of active streams')
tautulli_bandwidth = Gauge('neonboard_tautulli_bandwidth_kbps', 'Total bandwidth usage in kbps')
tautulli_transcodes = Gauge('neonboard_tautulli_active_transcodes', 'Number of active transcodes')

# System
cpu_usage = Gauge('neonboard_cpu_usage_percent', 'CPU usage in percent')
ram_usage = Gauge('neonboard_ram_usage_percent', 'RAM usage in percent')
uptime_gauge = Gauge('neonboard_system_uptime_seconds', 'System uptime in seconds')
cpu_cores = Gauge('neonboard_cpu_cores', 'Number of physical CPU cores')
cpu_threads = Gauge('neonboard_cpu_threads', 'Number of logical threads')
cpu_sockets = Gauge('neonboard_cpu_sockets', 'Estimated number of CPU sockets')
cpu_base_freq = Gauge('neonboard_cpu_base_frequency_mhz', 'CPU base frequency in MHz')

# Disks
disk_root_usage = Gauge('neonboard_disk_root_usage_percent', 'Disk usage for /')
disk_downloads_usage = Gauge('neonboard_disk_downloads_usage_percent', 'Disk usage for qBittorrent download directory')

# Temperaturer
cpu_temp = Gauge('neonboard_temperature_cpu_celsius', 'CPU temperature in Celsius')
gpu_temp = Gauge('neonboard_temperature_gpu_celsius', 'GPU temperature in Celsius')

# Top processer
top_cpu_usage = Gauge('neonboard_top_cpu_process_usage_percent', 'CPU usage of top processes', ['pid', 'name'])
top_mem_usage = Gauge('neonboard_top_mem_process_usage_mb', 'Memory usage of top processes in MB', ['pid', 'name'])


def get_qbittorrent_download_dir():
    try:
        session = requests.Session()
        session.post(f"{QBITTORRENT_URL}/api/v2/auth/login", data={
            'username': QBITTORRENT_USERNAME,
            'password': QBITTORRENT_PASSWORD
        })

        res = session.get(f"{QBITTORRENT_URL}/api/v2/app/preferences")
        res.raise_for_status()
        return res.json().get('save_path', '/mnt/local/downloads')
    except Exception as e:
        print(f"[WARN] Failed to get qBittorrent download path: {e}")
        return '/mnt/local/downloads'


def get_cpu_temp():
    try:
        out = subprocess.check_output("sensors", text=True)
        for line in out.splitlines():
            if "Package id 0" in line or "Tctl" in line:
                return float(line.split()[-2].replace("+", "").replace("°C", ""))
    except Exception:
        return None


def get_gpu_temp():
    try:
        out = subprocess.check_output("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", shell=True, text=True)
        return float(out.strip())
    except Exception:
        return None


def collect_metrics():
    # CPU og RAM
    cpu_usage.set(psutil.cpu_percent(interval=1))
    ram_usage.set(psutil.virtual_memory().percent)
    uptime_gauge.set(time.time() - psutil.boot_time())

    # CPU info
    cpu_cores.set(psutil.cpu_count(logical=False))
    cpu_threads.set(psutil.cpu_count(logical=True))
    cpu_sockets.set(len(set(psutil.cpu_freq(percpu=True))))
    try:
        cpu_base_freq.set(psutil.cpu_freq().min)
    except Exception:
        pass

    # Disk
    try:
        disk_root_usage.set(psutil.disk_usage("/").percent)
        downloads_path = get_qbittorrent_download_dir()
        disk_downloads_usage.set(psutil.disk_usage(downloads_path).percent)
    except Exception as e:
        print(f"[WARN] Disk usage collection failed: {e}")

    # Temperaturer
    cpu = get_cpu_temp()
    if cpu is not None:
        cpu_temp.set(cpu)
    gpu = get_gpu_temp()
    if gpu is not None:
        gpu_temp.set(gpu)

    # Top processer
    processes = [(p.pid, p.info) for p in psutil.process_iter(['name', 'cpu_percent', 'memory_info'])]
    top_cpu = sorted(processes, key=lambda x: x[1]['cpu_percent'], reverse=True)[:5]
    top_mem = sorted(processes, key=lambda x: x[1]['memory_info'].rss, reverse=True)[:5]

    for pid, info in top_cpu:
        top_cpu_usage.labels(pid=str(pid), name=info['name']).set(info['cpu_percent'])

    for pid, info in top_mem:
        mem_mb = info['memory_info'].rss / 1024 / 1024
        top_mem_usage.labels(pid=str(pid), name=info['name']).set(mem_mb)


def collect_tautulli():
    try:
        res = requests.get(f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity", timeout=5)
        data = res.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])

        streams = len(sessions)
        bandwidth = sum(int(s.get("wan_bandwidth", 0)) for s in sessions)
        transcodes = sum(1 for s in sessions if s.get("transcode_decision") == "transcode")

        tautulli_streams.set(streams)
        tautulli_bandwidth.set(bandwidth)
        tautulli_transcodes.set(transcodes)
    except Exception as e:
        print(f"[WARN] Failed to collect Tautulli metrics: {e}")
        tautulli_streams.set(0)
        tautulli_bandwidth.set(0)
        tautulli_transcodes.set(0)


@app.route("/metrics")
def metrics():
    collect_metrics()
    collect_tautulli()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    print(f"Starting NeonBoard Exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
