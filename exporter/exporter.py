from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import psutil
import shutil
import platform
import time
import os
import requests
import json
import subprocess

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
    # Tautulli
    "tautulli_active_streams": Gauge(
        "tautulli_active_streams", "Number of active streams"
    ),
    "tautulli_bandwidth_total_kbps": Gauge(
        "tautulli_bandwidth_total_kbps", "Total bandwidth usage in kbps"
    ),
    "tautulli_transcodes_active": Gauge(
        "tautulli_transcodes_active", "Number of active transcodes"
    ),
    # System
    "neonboard_cpu_usage_percent": Gauge(
        "neonboard_cpu_usage_percent", "Current CPU usage in percent"
    ),
    "neonboard_ram_usage_percent": Gauge(
        "neonboard_ram_usage_percent", "Current RAM usage in percent"
    ),
    "neonboard_uptime_seconds": Gauge(
        "neonboard_uptime_seconds", "System uptime in seconds"
    ),
    "neonboard_cpu_base_mhz": Gauge(
        "neonboard_cpu_base_mhz", "CPU base clock speed in MHz"
    ),
    "neonboard_cpu_sockets": Gauge(
        "neonboard_cpu_sockets", "Number of physical CPU sockets"
    ),
    "neonboard_cpu_cores": Gauge("neonboard_cpu_cores", "Number of physical CPU cores"),
    "neonboard_cpu_threads": Gauge(
        "neonboard_cpu_threads", "Number of logical CPU threads"
    ),
    "neonboard_load_1": Gauge("neonboard_load_1", "System load average over 1 minute"),
    "neonboard_load_5": Gauge("neonboard_load_5", "System load average over 5 minutes"),
    "neonboard_load_15": Gauge(
        "neonboard_load_15", "System load average over 15 minutes"
    ),
    # Disk (root)
    "neonboard_disk_root_bytes_free": Gauge(
        "neonboard_disk_root_bytes_free", "Free disk space on / in bytes"
    ),
    "neonboard_disk_root_bytes_total": Gauge(
        "neonboard_disk_root_bytes_total", "Total disk space on / in bytes"
    ),
    "neonboard_disk_root_bytes_used": Gauge(
        "neonboard_disk_root_bytes_used", "Used disk space on / in bytes"
    ),
    "neonboard_disk_root_percent_free": Gauge(
        "neonboard_disk_root_percent_free", "Free disk space on / in percent"
    ),
    # Disk (downloads)
    "neonboard_disk_downloads_bytes_free": Gauge(
        "neonboard_disk_downloads_bytes_free",
        "Free disk space on downloads mount in bytes",
    ),
    "neonboard_disk_downloads_bytes_total": Gauge(
        "neonboard_disk_downloads_bytes_total",
        "Total disk space on downloads mount in bytes",
    ),
    "neonboard_disk_downloads_bytes_used": Gauge(
        "neonboard_disk_downloads_bytes_used",
        "Used disk space on downloads mount in bytes",
    ),
    "neonboard_disk_downloads_percent_free": Gauge(
        "neonboard_disk_downloads_percent_free",
        "Free disk space on downloads in percent",
    ),
    # Temperatures
    "neonboard_temp_cpu_core": Gauge(
        "neonboard_temp_cpu_core", "CPU core temperature in Celsius", ["core"]
    ),
    "neonboard_temp_chipset": Gauge(
        "neonboard_temp_chipset", "Chipset temperature in Celsius"
    ),
    "neonboard_temp_nvme": Gauge(
        "neonboard_temp_nvme", "NVMe temperature in Celsius", ["device"]
    ),
    "neonboard_temp_disk": Gauge(
        "neonboard_temp_disk", "Disk temperature in Celsius", ["device"]
    ),
    # Top processes
    "neonboard_top_cpu_process_percent": Gauge(
        "neonboard_top_cpu_process_percent", "Top process CPU usage", ["name", "pid"]
    ),
    "neonboard_top_ram_process_mb": Gauge(
        "neonboard_top_ram_process_mb", "Top process RAM usage in MB", ["name", "pid"]
    ),
}


def get_qbit_download_path():
    try:
        session = requests.Session()
        session.post(
            f"{QBIT_URL}/api/v2/auth/login",
            data={"username": QBIT_USER, "password": QBIT_PASS},
            timeout=5,
        )
        r = session.get(f"{QBIT_URL}/api/v2/app/preferences", timeout=5)
        data = r.json()
        return data.get("save_path", "/mnt/local/downloads")
    except Exception as e:
        print(f"[WARNING] Failed to get qBittorrent download path: {e}")
        return "/mnt/local/downloads"


@app.route("/metrics")
def metrics():
    # =============== Tautulli ===================
    try:
        r = requests.get(
            f"{TAUTULLI_URL}/api/v2?apikey={TAUTULLI_API_KEY}&cmd=get_activity",
            timeout=5,
        )
        data = r.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])

        gauges["tautulli_active_streams"].set(len(sessions))
        gauges["tautulli_bandwidth_total_kbps"].set(
            sum(int(s.get("wan_bandwidth", 0)) for s in sessions)
        )
        gauges["tautulli_transcodes_active"].set(
            sum(1 for s in sessions if s.get("transcode_decision") == "transcode")
        )
    except Exception as e:
        print(f"[WARNING] Failed to fetch Tautulli metrics: {e}")

    # =============== System ===================
    try:
        gauges["neonboard_cpu_usage_percent"].set(psutil.cpu_percent(interval=1))
        gauges["neonboard_ram_usage_percent"].set(psutil.virtual_memory().percent)
        gauges["neonboard_uptime_seconds"].set(time.time() - psutil.boot_time())
        gauges["neonboard_cpu_base_mhz"].set(psutil.cpu_freq().max)
        gauges["neonboard_cpu_cores"].set(psutil.cpu_count(logical=False))
        gauges["neonboard_cpu_threads"].set(psutil.cpu_count(logical=True))
        gauges["neonboard_load_1"].set(os.getloadavg()[0])
        gauges["neonboard_load_5"].set(os.getloadavg()[1])
        gauges["neonboard_load_15"].set(os.getloadavg()[2])

        # Antal sockets via lscpu
        try:
            result = subprocess.run(
                ["lscpu"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "Socket(s):" in line:
                    sockets = int(line.split(":")[1].strip())
                    gauges["neonboard_cpu_sockets"].set(sockets)
                    break
        except Exception as e:
            print(f"[WARNING] Could not parse sockets from lscpu: {e}")

        # Root disk
        root_usage = shutil.disk_usage("/")
        gauges["neonboard_disk_root_bytes_free"].set(root_usage.free)
        gauges["neonboard_disk_root_bytes_total"].set(root_usage.total)
        gauges["neonboard_disk_root_bytes_used"].set(root_usage.used)
        gauges["neonboard_disk_root_percent_free"].set(
            (root_usage.free / root_usage.total) * 100
        )

        # Downloads disk
        downloads_path = get_qbit_download_path()
        try:
            downloads_usage = shutil.disk_usage(downloads_path)
        except Exception:
            downloads_usage = shutil._ntuple_diskusage(0, 0, 0)

        gauges["neonboard_disk_downloads_bytes_free"].set(downloads_usage.free)
        gauges["neonboard_disk_downloads_bytes_total"].set(downloads_usage.total)
        gauges["neonboard_disk_downloads_bytes_used"].set(downloads_usage.used)
        if downloads_usage.total > 0:
            gauges["neonboard_disk_downloads_percent_free"].set(
                (downloads_usage.free / downloads_usage.total) * 100
            )

        # Top processes
        processes = [
            (
                p.info["name"],
                p.pid,
                p.info["cpu_percent"],
                p.info["memory_info"].rss / 1024 / 1024,
            )
            for p in psutil.process_iter(["name", "cpu_percent", "memory_info"])
        ]

        for name, pid, cpu, mem in sorted(processes, key=lambda x: x[2], reverse=True)[
            :5
        ]:
            gauges["neonboard_top_cpu_process_percent"].labels(
                name=name, pid=str(pid)
            ).set(cpu)

        for name, pid, cpu, mem in sorted(processes, key=lambda x: x[3], reverse=True)[
            :5
        ]:
            gauges["neonboard_top_ram_process_mb"].labels(name=name, pid=str(pid)).set(
                mem
            )

        # Temperatures
        temps = psutil.sensors_temperatures()
        if "coretemp" in temps:
            for t in temps["coretemp"]:
                label = t.label or f"core{t._source_index}"
                gauges["neonboard_temp_cpu_core"].labels(core=label).set(t.current)

        if "nvme" in temps:
            for t in temps["nvme"]:
                gauges["neonboard_temp_nvme"].labels(device=t.label or "nvme").set(
                    t.current
                )

        if "acpitz" in temps:
            for t in temps["acpitz"]:
                gauges["neonboard_temp_chipset"].set(t.current)

        if "hddtemp" in temps or "sd" in temps:
            key = "hddtemp" if "hddtemp" in temps else "sd"
            for t in temps[key]:
                gauges["neonboard_temp_disk"].labels(device=t.label or "disk").set(
                    t.current
                )

    except Exception as e:
        print(f"[ERROR] System metrics failed: {e}")

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    print(f"Starting NeonBoard Exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
