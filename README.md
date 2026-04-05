# Heartbeat Sidecar - Instructions for other teams

The sidecar monitors whether your containers are reachable and sends a heartbeat to RabbitMQ every second. The monitoring team processes these messages and displays the status in Kibana.

---

## What you need to do

Add the following service to your `docker-compose.yml`:

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

> **Monitoring multiple containers?** Specify all of them in `TARGETS`, separated by a comma:
> ```
> TARGETS=api:8080,worker:9000,database:5432
> ```
> If even one container is unreachable, the sidecar will stop sending heartbeats for the entire system.

---

## Environment variables

| Variable | Required | Description |
|----------|-----------|--------------|
| `SYSTEM_NAME` | yes | Unique name for your system (e.g. `facturatie`, `crm`, `planning`) |
| `TARGETS` | yes | Comma-separated list of `container-naam:poort` pairs to monitor |
| `RABBITMQ_HOST` | yes | Hostname of RabbitMQ (in the shared environment: `rabbitmq_broker`) |
| `RABBITMQ_USER` | yes | RabbitMQ username (provided by Tom) |
| `RABBITMQ_PASS` | yes | RabbitMQ password (provided by Tom) |
| `RABBITMQ_VHOST` | no | RabbitMQ virtual host (default: `/`) |

---

## Requirements

- Every container specified in `TARGETS` must have a **reachable TCP port**.
- he sidecar container must be on the **same Docker network** as your app containers and RabbitMQ.

---

## Image updates

The image is automatically built and published via GitHub Actions with every new release (tag). The Infrastructure Team manages deployments on the VM via Watchtower — new versions are automatically picked up and rolled out. You do not need to take any action for this yourselves.
