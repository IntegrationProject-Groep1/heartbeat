import socket
import ipaddress
import time
import os
import sys
import uuid
import pika
import xml.etree.ElementTree as ET
import logging
import json
import signal
import threading
import queue
from datetime import datetime, timezone
from lxml import etree

# --- Structured JSON Logging Setup ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "message": record.getMessage(),
            "system": os.environ.get("SYSTEM_NAME", "unknown")
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

# Suppress noisy pika logs
logging.getLogger("pika").setLevel(logging.WARNING)

# --- Configuration ---
SYSTEM_NAME = os.environ.get("SYSTEM_NAME")
TARGETS_RAW = os.environ.get("TARGETS", "")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")
XSD_PATH = "heartbeat.xsd"

if not all([SYSTEM_NAME, TARGETS_RAW, RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS]):
    logger.error("FOUT: stel alle environment variables in")
    sys.exit(1)

try:
    TARGETS = []
    for t in TARGETS_RAW.split(","):
        host, port_str = t.strip().rsplit(":", 1)
        TARGETS.append((host, int(port_str)))
except (ValueError, IndexError):
    logger.error("FOUT: TARGETS heeft een ongeldig formaat. Verwacht: host:port[,host:port,...]")
    sys.exit(1)

# Global State
alive_since = None
last_down_log_time = 0
msg_queue = queue.Queue()
running = True

# --- XSD Validation ---
if os.path.exists(XSD_PATH):
    try:
        with open(XSD_PATH, 'rb') as _f:
            _schema = etree.XMLSchema(etree.XML(_f.read()))
    except Exception as e:
        logger.error(f"Fout bij laden van XSD: {e}")
        _schema = None
else:
    logger.warning(f"{XSD_PATH} niet gevonden. Validatie overgeslagen.")
    _schema = None

def validate_xml(xml_string):
    if _schema is None:
        return True
    try:
        _schema.assertValid(etree.fromstring(xml_string.encode('utf-8')))
        return True
    except Exception as e:
        logger.error(f"XSD Validatie fout: {e}")
        return False

# --- Core Functions ---
def is_alive(host, port, timeout=2):
    try:
        # Resolve address to handle both hostnames and IPs
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET)
        if not addr_info:
            return False
        ip = addr_info[0][4][0]
        
        # Security check: only private IPs allowed
        if not ipaddress.ip_address(ip).is_private:
            return False
            
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError, socket.gaierror):
        return False

def build_heartbeat_xml(system_name, status, uptime):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    message = ET.Element("message")

    header = ET.SubElement(message, "header")
    ET.SubElement(header, "message_id").text = str(uuid.uuid4())
    ET.SubElement(header, "timestamp").text = timestamp
    ET.SubElement(header, "source").text = system_name
    ET.SubElement(header, "type").text = "heartbeat"
    ET.SubElement(header, "version").text = "2.0"

    body = ET.SubElement(message, "body")
    ET.SubElement(body, "status").text = status
    ET.SubElement(body, "uptime").text = str(uptime)

    return ET.tostring(message, encoding='unicode')

# --- Publisher Thread ---
def publisher_worker():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = None
    channel = None

    def connect():
        while running:
            try:
                conn = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RABBITMQ_HOST, virtual_host=RABBITMQ_VHOST, credentials=credentials)
                )
                chan = conn.channel()
                chan.queue_declare(queue="heartbeat", durable=True)
                logger.info("Verbonden met RabbitMQ")
                return conn, chan
            except pika.exceptions.AMQPConnectionError:
                logger.error("RabbitMQ niet bereikbaar, opnieuw proberen in 5 sec")
                threading.Event().wait(5)
        return None, None

    connection, channel = connect()

    while running or not msg_queue.empty():
        try:
            # Wait for a message with a timeout so we can check 'running' flag
            xml = msg_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            try:
                if channel and channel.is_open:
                    channel.basic_publish(
                        exchange="",
                        routing_key="heartbeat",
                        body=xml.encode('utf-8'),
                        properties=pika.BasicProperties(delivery_mode=2)
                    )
                else:
                    raise pika.exceptions.AMQPError("Connection/Channel not available")
            except (pika.exceptions.AMQPError, pika.exceptions.ChannelClosedByBroker):
                logger.error("RabbitMQ verbinding verloren, opnieuw verbinden")
                if connection:
                    try:
                        connection.close()
                    except Exception:
                        pass
                connection, channel = connect()
                if channel:
                    channel.basic_publish(
                        exchange="",
                        routing_key="heartbeat",
                        body=xml.encode('utf-8'),
                        properties=pika.BasicProperties(delivery_mode=2)
                    )
        except Exception as e:
            logger.error(f"Onverwachte fout in publisher thread: {e}", exc_info=True)
        finally:
            msg_queue.task_done()

    if connection and connection.is_open:
        connection.close()

# --- Signal Handling ---
def handle_sigterm(signum, frame):
    global running
    logger.info("SIGTERM ontvangen. Bezig met netjes afsluiten...")
    
    # Send final "offline" heartbeat as requested for graceful shutdown notification
    uptime_seconds = int(time.monotonic() - alive_since) if alive_since else 0
    xml = build_heartbeat_xml(SYSTEM_NAME, "offline", uptime_seconds)
    
    if validate_xml(xml):
        msg_queue.put(xml)
    
    # Stop the main loops and let threads exit after processing remaining messages
    running = False

signal.signal(signal.SIGTERM, handle_sigterm)

# --- Main Execution ---
logger.info(f"Sidecar gestart voor systeem: {SYSTEM_NAME}")
logger.info(f"Controleert: {', '.join(f'{h}:{p}' for h, p in TARGETS)}")

pub_thread = threading.Thread(target=publisher_worker, daemon=True)
pub_thread.start()

while running:
    start_time = time.monotonic()
    
    failed_targets = [f"{host}:{port}" for host, port in TARGETS if not is_alive(host, port)]
    
    if not failed_targets:
        if alive_since is None:
            alive_since = time.monotonic()
            logger.info("Alle targets bereikbaar. Systeem is ONLINE.")
        
        uptime_seconds = int(time.monotonic() - alive_since)
        xml = build_heartbeat_xml(SYSTEM_NAME, "online", uptime_seconds)
        
        if validate_xml(xml):
            # Non-blocking: put message in queue and continue loop immediately
            msg_queue.put(xml)
    else:
        if alive_since is not None:
            logger.error(f"[DOWN] {SYSTEM_NAME} niet bereikbaar: {', '.join(failed_targets)}")
            alive_since = None
            last_down_log_time = time.monotonic()
        else:
            # Still down: log locally but do not send XML to RabbitMQ (Dead Man's Switch)
            now = time.monotonic()
            if now - last_down_log_time >= 60:
                logger.error(f"[STILL DOWN] Wacht op herstel: {', '.join(failed_targets)}")
                last_down_log_time = now


    # Ensure strict 1-second interval
    work_duration = time.monotonic() - start_time
    if work_duration < 1:
        time.sleep(1 - work_duration)
