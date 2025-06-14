# Tautulli Prometheus Exporter

![Docker](https://img.shields.io/badge/build-passing-brightgreen)  
Prometheus exporter til Tautulli. Dette Docker-baserede exporter-script henter metrics direkte fra Tautulli API'en og eksponerer dem i Prometheus-format til Grafana-overvågning.

## 🧩 Features

- Henter live data fra Tautulli (aktive streams, brugere, play counts, osv.)
- Eksponerer metrics på `/metrics` endpoint
- Designet til nem integration med Prometheus og Grafana
- Kører som letvægts Python-webserver (Flask)
- Docker-support med GHCR builds via GitHub Actions

## 🚀 Docker Image

Find Docker-imaget her:
```
ghcr.io/neongod78/tautulli-prometheus-exporter:latest
```

## ⚙️ Miljøvariabler

| Variable           | Description                             | Required |
|--------------------|-----------------------------------------|----------|
| `TAUTULLI_URL`     | URL til din Tautulli-server             | ✅       |
| `TAUTULLI_APIKEY`  | API-nøgle genereret i Tautulli settings | ✅       |
| `PORT`             | Port som exporter skal køre på          | ❌ (default: `9799`) |

## 🐳 Eksempel docker-compose

```yaml
services:
  tautulli_exporter:
    image: ghcr.io/neongod78/tautulli-prometheus-exporter:latest
    container_name: tautulli_exporter
    restart: unless-stopped
    ports:
      - 9799:9799
    environment:
      - TAUTULLI_URL=http://tautulli:8181
      - TAUTULLI_APIKEY=your_api_key_here
```

## 📊 Grafana Dashboard

Importer følgende Prometheus-paneler i Grafana:

- Aktive streams
- Brugere i gang
- Top brugere
- Daglige visninger

(Et færdigt dashboard JSON uploades senere her i repoet.)

## 📦 Build og udvikling

Du kan bygge din egen image lokalt:

```bash
docker build -t tautulli-prometheus-exporter .
```

## 📝 Licens

MIT License – se [LICENSE](LICENSE)

---

Made with ❤️ by [NeonGOD78](https://github.com/NeonGOD78)
