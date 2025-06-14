# NeonBoard Exporter

![Docker Image Version](https://img.shields.io/badge/docker-latest-blue)
![License](https://img.shields.io/github/license/NeonGOD78/neonboard)

Prometheus-compatible metrics exporter written in Python. This exporter serves as the unified backend for NeonBoard, collecting data from multiple sources:

- Tautulli (for Plex stream metrics)
- System metrics (CPU, RAM, Disk)
- Disk space (including root and download directories)
- Temperature data (CPU, NVMe, GPU, etc.)
- More to come...

## Features

- Lightweight Python Flask app
- Self-contained metrics endpoint at `/metrics`
- Reads configuration via environment variables
- Easily extendable with new metrics

## Usage

Docker Compose example:

```yaml
services:
  neonboard_exporter:
    image: ghcr.io/neongod78/neonboard-exporter:latest
    container_name: neonboard_exporter
    environment:
      - TAUTULLI_API_KEY=your_api_key
      - TAUTULLI_URL=http://tautulli:8181
    ports:
      - 9814:9814
    restart: unless-stopped
```

Prometheus scrape config:

```yaml
  - job_name: 'neonboard_exporter'
    static_configs:
      - targets: ['neonboard_exporter:9814']
```

## Endpoints

- `/metrics` - returns Prometheus formatted metrics

## License

This project is licensed under the MIT License.
