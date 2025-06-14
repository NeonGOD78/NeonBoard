from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import requests
import os

app = Flask(__name__)

# Miljøvariabler
API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9861"))

# Prometheus metrics
active_streams_gauge = Gauge('tautulli_active_streams', 'Number of active streams')
bandwidth_gauge = Gauge('tautulli_bandwidth_total', 'Total bandwidth usage in kbps')
transcodes_gauge = Gauge('tautulli_transcodes_active', 'Number of active transcodes')

@app.route("/metrics")
def metrics():
    try:
        response = requests.get(
            f"{TAUTULLI_URL}/api/v2?apikey={API_KEY}&cmd=get_activity",
            timeout=5
        )
        data = response.json()
        sessions = data.get("response", {}).get("data", {}).get("sessions", [])

        active_streams = len(sessions)
        total_bandwidth = 0
        active_transcodes = 0

        for session in sessions:
            total_bandwidth += int(session.get("wan_bandwidth", 0))
            if session.get("transcode_decision") == "transcode":
                active_transcodes += 1

        # Opdater metrics
        active_streams_gauge.set(active_streams)
        bandwidth_gauge.set(total_bandwidth)
        transcodes_gauge.set(active_transcodes)

    except Exception as e:
        print(f"[ERROR] Failed to collect metrics: {e}")
        active_streams_gauge.set(0)
        bandwidth_gauge.set(0)
        transcodes_gauge.set(0)

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    print(f"Starting Tautulli exporter on port {EXPORTER_PORT}")
    app.run(host="0.0.0.0", port=EXPORTER_PORT)
