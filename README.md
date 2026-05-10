# Heartbeat Sidecar - Instructions for other teams

The sidecar monitors whether your containers are reachable and sends a heartbeat to RabbitMQ every second. It is optimized for Kubernetes environments and uses a **Dead Man's Switch** pattern for reliability.

---

## What you need to do

Add the following service to your `docker-compose.yml` (or as a sidecar container in your Kubernetes Pod):

```yaml
sidecar:
  image: ghcr.io/integrationproject-groep1/heartbeat:latest
  environment:
    - SYSTEM_NAME=jullie-systeem-naam
    - TARGETS=127.0.0.1:8080  # Since it's in the same pod, use localhost!
    - RABBITMQ_HOST=rabbitmq_broker
    - RABBITMQ_USER=<gebruikersnaam>
    - RABBITMQ_PASS=<wachtwoord>
    - RABBITMQ_VHOST=/
```

> **Note on Failure Detection**: 
> If one of your targets goes down, the sidecar will **stop sending heartbeats**. The Monitoring Team's Kibana alerts will detect this absence and notify administrators. This ensures that even if the sidecar itself crashes, a failure is reported.

---

## Environment variables

| Variable | Required | Description |
|----------|-----------|--------------|
| `SYSTEM_NAME` | yes | Unique name for your system (e.g. `facturatie`, `crm`, `planning`) |
| `TARGETS` | yes | Comma-separated list of `host:port` pairs to monitor. In K8s, prefer `127.0.0.1:port`. |
| `RABBITMQ_HOST` | yes | Hostname of RabbitMQ. |
| `RABBITMQ_USER` | yes | RabbitMQ username. |
| `RABBITMQ_PASS` | yes | RabbitMQ password. |
| `RABBITMQ_VHOST` | no | RabbitMQ virtual host (default: `/`) |

---

## Architecture & Signals

- **Interval**: Fixed at 1 heartbeat per second.
- **Graceful Shutdown**: The sidecar intercepts `SIGTERM`. Before shutting down, it sends one final XML message with `<status>offline</status>` to inform the monitoring team that the stoppage was intentional (e.g., during a deployment).
- **Logging**: All logs are output in JSON format to `stdout`.

## Requirements

- Every container specified in `TARGETS` must have a **reachable TCP port**.
- For Kubernetes: The sidecar must run in the **same Pod** as your application containers.
- For Docker Compose: The sidecar must be on the **same Docker network** as your app containers and RabbitMQ.

---

## Image updates

The image is automatically built and published via GitHub Actions with every new release (tag). The Infrastructure Team manages deployments via automated pipelines.
