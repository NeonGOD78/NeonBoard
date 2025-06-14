# NeonBoard Dashboard

Dette er Grafana-dashboardet til **NeonBoard** – et omfattende overvågningspanel til din medieserver.

## Funktioner

- CPU- og RAM-overvågning
- Diskforbrug (root og qBittorrent-downloads)
- Systemtemperaturer (CPU, NVMe, disks, GPU, chipset)
- Aktiv Plex/Tautulli-streaming
- Containerstatus og tjenestetilgængelighed
- Integreret Cockpit-launch-knap

## Krav

Dashboardet er designet til at fungere sammen med:
- [NeonBoard Exporter](../exporter)
- Prometheus
- Grafana

## Datasources

Dashboardet bruger følgende Prometheus jobs:
- `node_exporter`
- `tautulli_exporter` (NeonBoard Exporter)
- `cadvisor`
- `qbittorrent_exporter`
- `exportarr_sonarr`
- `exportarr_radarr`

## Import

1. Åbn Grafana → Dashboards → New → Import.
2. Upload `neonboard-dashboard.json` eller indsæt ID hvis du har uploaded det til Grafana Cloud.
3. Vælg korrekt Prometheus datasource.
4. Klik **Import**.

## Tilpasning

Du kan selv tilpasse farver, layout og paneler. Flere features planlægges i takt med at eksporteren udvides.

## Licens

MIT License – se [../LICENSE](../LICENSE)
