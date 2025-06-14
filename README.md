# NeonBoard

[![Docker Image CI](https://github.com/NeonGOD78/NeonBoard/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/NeonGOD78/NeonBoard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboard-blue?logo=grafana)](https://grafana.com/)

**NeonBoard** er et samlet overvågningssystem, som kombinerer en custom Prometheus-exporter og et Grafana-dashboard til overvågning af medieservermiljøer (Plex, Sonarr, Radarr, qBittorrent m.m.) og systemstatus (CPU, RAM, diske, temperaturer, containere osv.).

## 🧠 Funktioner

- Custom exporter til:
  - Aktive Plex (Tautulli) streams
  - CPU/RAM-forbrug
  - Diskplads på root og downloads-mount
  - Temperaturer (CPU, NVMe, disks, chipset, GPU)
- Grafana-dashboard med moderne layout:
  - Graf for CPU
  - Gauge for RAM
  - Diskplads-visualisering
  - Temperaturvisning
  - Knap til Cockpit

---

## 🚀 Opsætning

### 1. Klon repoet

```bash
git clone git@github.com:NeonGOD78/NeonBoard.git
cd NeonBoard
```

### 2. Opsæt Docker-container

Tilføj til din `docker-compose.yml`:

```yaml
neonboard_exporter:
  build: ./NeonBoard/exporter
  container_name: neonboard_exporter
  environment:
    - TAUTULLI_API_KEY=din_api_nøgle
    - TAUTULLI_URL=http://tautulli:8181
  ports:
    - 9861:9861
  restart: unless-stopped
  networks:
    - proxy
```

> Justér `TAUTULLI_URL` og netværk efter behov.

### 3. Tilføj til `prometheus.yml`

```yaml
- job_name: 'neonboard'
  static_configs:
    - targets: ['neonboard_exporter:9861']
```

### 4. Importér Grafana-dashboard

Dashboard JSON findes i `NeonBoard/dashboard/NeonBoard.json` og kan importeres via Grafana UI.

---

## 🖥️ Dashboard preview

![Preview](assets/preview.png)

---

## 📦 Struktur

```text
NeonBoard/
├── dashboard/
│   └── NeonBoard.json
├── exporter/
│   ├── exporter.py
│   └── Dockerfile
└── README.md
```

---

## 📃 Licens

MIT License
