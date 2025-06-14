import os
import requests
from flask import Flask, Response

app = Flask(__name__)

TAUTULLI_APIKEY = os.getenv("TAUTULLI_APIKEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://localhost:8181")

@app.route("/metrics")
def metrics():
    try:
        response = requests.get(f"{TAUTULLI_URL}/api/v2", params={
            "apikey": TAUTULLI_APIKEY,
            "cmd": "get_activity"
        })
        data = response.json()["response"]["data"]

        sessions = data.get("sessions", [])
        active_streams = len(sessions)
        transcodes = sum(1 for s in sessions if s.get("transcode_decision") == "transcode")
        bandwidth = sum(int(s.get("bandwidth", 0)) for s in sessions)

        metrics_output = [
            f"tautulli_active_streams {active_streams}",
            f"tautulli_transcodes_active {transcodes}",
            f"tautulli_bandwidth_total {bandwidth}"
        ]

        user_count = {}
        for s in sessions:
            user = s.get("username", "unknown")
            user_count[user] = user_count.get(user, 0) + 1
        for user, count in user_count.items():
            metrics_output.append(f'tautulli_user_streams{{user="{user}"}} {count}')

        return Response("\n".join(metrics_output), mimetype="text/plain")

    except Exception as e:
        return Response(f"# Error: {str(e)}", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9814)
