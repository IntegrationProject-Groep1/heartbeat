# Sidecar Test Setup

This folder contains everything needed to test the sidecar locally. It spins up three containers:
- **rabbitmq** — the message broker the sidecar sends heartbeats to
- **target** — a dummy nginx container that the sidecar monitors (just needs an open TCP port)
- **sidecar** — the actual service being tested

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Python 3 installed on your machine
- `pika` Python package: run `pip install pika` once before starting

---

## Step 1 — Start the test environment

Open a terminal, navigate to this folder, and run:

```
docker compose -f docker-compose.test.yml up --build
```

Docker will:
1. Build the sidecar image
2. Start RabbitMQ (takes ~20 seconds to be fully ready)
3. Start nginx (target)
4. Start the sidecar once RabbitMQ is healthy

You will see output from all three containers. When you see `Verbonden met RabbitMQ`, the sidecar is running and sending heartbeats.

---

## Step 2 — Read the messages

Open a **second terminal**, navigate to this folder, and run:

```
python consumer.py
```

You should see a new message every second, like this:

```
Waiting for messages on queue 'heartbeat'. Press CTRL+C to stop.

--- Message received ---
<heartbeat><system>test-system</system><timestamp>2026-03-29T14:30:45Z</timestamp><uptime>3</uptime></heartbeat>

--- Message received ---
<heartbeat><system>test-system</system><timestamp>2026-03-29T14:30:46Z</timestamp><uptime>4</uptime></heartbeat>
```

Press `CTRL+C` to stop the consumer.

---

## Step 3 (optional) — Test what happens when the target goes down

In a **third terminal**, stop the target container:

```
docker compose -f docker-compose.test.yml stop target
```

In the first terminal (compose logs) you will see:
```
[DOWN] test-system niet bereikbaar: target:80
```

The consumer will stop receiving messages. The `uptime` counter resets to 0.

Bring the target back up:

```
docker compose -f docker-compose.test.yml start target
```

Messages resume within a second, with `<uptime>1</uptime>`.

---

## Step 4 (optional) — Use the RabbitMQ management UI

Open your browser and go to: `http://localhost:15672`

Login: `testuser` / `testpass`

Go to **Queues** and select `heartbeat` to see the message rate and queue depth in real time.

---

## Step 5 — Stop everything

```
docker compose -f docker-compose.test.yml down
```

This stops and removes all containers.
