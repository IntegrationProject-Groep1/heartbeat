# Heartbeat Sidecar - Instructies voor andere teams

De sidecar bewaakt of jullie containers bereikbaar zijn en stuurt elke seconde een heartbeat naar RabbitMQ. Het monitoringteam verwerkt deze berichten en toont de status in Kibana.

---

## Wat jullie moeten doen

Voeg de volgende service toe aan jullie `docker-compose.yml`:

```yaml
sidecar:
  image: ghcr.io/integrationproject-groep1/heartbeat:latest
  environment:
    - SYSTEM_NAME=jullie-systeem-naam
    - TARGETS=jullie-container-naam:80
    - RABBITMQ_HOST=rabbitmq_broker
    - RABBITMQ_USER=<gebruikersnaam>
    - RABBITMQ_PASS=<wachtwoord>
    - RABBITMQ_VHOST=/
  depends_on:
    - jullie-container-naam
    - rabbitmq
```

> **Meerdere containers bewaken?** Geef ze allemaal op in `TARGETS`, gescheiden door een komma:
> ```
> TARGETS=api:8080,worker:9000,database:5432
> ```
> Als één container niet bereikbaar is, stopt de sidecar met het sturen van heartbeats voor het hele systeem.

---

## Environment variables

| Variable | Verplicht | Beschrijving |
|----------|-----------|--------------|
| `SYSTEM_NAME` | ja | Unieke naam voor jullie systeem (bijv. `facturatie`, `crm`, `planning`) |
| `TARGETS` | ja | Komma-gescheiden lijst van `container-naam:poort` paren om te bewaken |
| `RABBITMQ_HOST` | ja | Hostnaam van RabbitMQ (in de gedeelde omgeving: `rabbitmq_broker`) |
| `RABBITMQ_USER` | ja | RabbitMQ gebruikersnaam (wordt door Tom meegegeven) |
| `RABBITMQ_PASS` | ja | RabbitMQ wachtwoord (wordt door Tom meegegeven) |
| `RABBITMQ_VHOST` | nee | RabbitMQ virtual host (standaard: `/`) |

---

## Vereisten

- Elke container die jullie opgeven in `TARGETS` moet een **bereikbare TCP-poort** hebben.
- De sidecar-container moet op **hetzelfde Docker-netwerk** zitten als jullie app-containers en RabbitMQ.

---

## Image updates

Het image wordt automatisch gebouwd en gepubliceerd via GitHub Actions bij elke nieuwe release (tag). Team Infrastructuur beheert de deployments op de VM via Watchtower — nieuwe versies worden automatisch opgepikt en uitgerold. Jullie hoeven hier zelf niets voor te doen.
