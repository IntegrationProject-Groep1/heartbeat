import socket
import ipaddress
import time
import os
import sys
import uuid
import pika
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from lxml import etree

SYSTEM_NAME = os.environ.get("SYSTEM_NAME")
TARGETS_RAW = os.environ.get("TARGETS", "")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")
XSD_PATH = "heartbeat.xsd"

if not all([SYSTEM_NAME, TARGETS_RAW, RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS]):
    print("FOUT: stel alle environment variables in")
    sys.exit(1)

try:
    TARGETS = []
    for t in TARGETS_RAW.split(","):
        host, port_str = t.strip().rsplit(":", 1)
        TARGETS.append((host, int(port_str)))
except (ValueError, IndexError):
    print("FOUT: TARGETS heeft een ongeldig formaat. Verwacht: host:port[,host:port,...]")
    sys.exit(1)

alive_since = None

if os.path.exists(XSD_PATH):
    with open(XSD_PATH, 'rb') as _f:
        _schema = etree.XMLSchema(etree.XML(_f.read()))
else:
    print(f"Waarschuwing: {XSD_PATH} niet gevonden. Validatie overgeslagen.")
    _schema = None

def validate_xml(xml_string):
    if _schema is None:
        return True
    try:
        _schema.assertValid(etree.fromstring(xml_string.encode('utf-8')))
        return True
    except Exception as e:
        print(f"XSD Validatie fout: {e}")
        return False

def is_alive(host, port, timeout=2):
    try:
        ip = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
        if not ipaddress.ip_address(ip).is_private:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def all_alive(targets):
    failed = [f"{host}:{port}" for host, port in targets if not is_alive(host, port)]
    if failed:
        print(f"[DOWN] {SYSTEM_NAME} niet bereikbaar: {', '.join(failed)}")
        return False
    return True


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


def connect_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, virtual_host=RABBITMQ_VHOST, credentials=credentials)
            )
            channel = connection.channel()
            channel.queue_declare(queue="heartbeat", durable=True)
            print("Verbonden met RabbitMQ")
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ niet bereikbaar, opnieuw proberen in 5 sec")
            time.sleep(5)


def publish(channel, xml):
    channel.basic_publish(
        exchange="",
        routing_key="heartbeat",
        body=xml.encode('utf-8'),
        properties=pika.BasicProperties(delivery_mode=2)
    )


print(f"Sidecar gestart voor systeem: {SYSTEM_NAME}")
print(f"Controleert: {', '.join(f'{h}:{p}' for h, p in TARGETS)}")

connection, channel = connect_rabbitmq()


while True:
    start_time = time.monotonic()
    if all_alive(TARGETS):
        if alive_since is None:
            alive_since = time.monotonic()
        uptime_seconds = int(time.monotonic() - alive_since)
        xml = build_heartbeat_xml(SYSTEM_NAME, "online", uptime_seconds)
    else:
        alive_since = None
        xml = build_heartbeat_xml(SYSTEM_NAME, "offline", 0)

    if validate_xml(xml):
        try:
            publish(channel, xml)
        except pika.exceptions.AMQPError:
            print("RabbitMQ verbinding verloren, opnieuw verbinden")
            try:
                connection.close()
            except Exception as e:
                print(f"Fout bij sluiten van RabbitMQ verbinding: {e}")
            connection, channel = connect_rabbitmq()

    work_duration = time.monotonic() - start_time
    if work_duration < 1:
        time.sleep(1 - work_duration)