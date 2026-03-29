import pika
import sys

RABBITMQ_HOST = "localhost"  # RabbitMQ port 5672 is forwarded to the host
RABBITMQ_USER = "testuser"
RABBITMQ_PASS = "testpass"
QUEUE = "heartbeat"


def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    )
    channel = connection.channel()

    # durable=True must match sidecar.py exactly - a mismatch causes a RabbitMQ error
    channel.queue_declare(queue=QUEUE, durable=True)

    print(f"Waiting for messages on queue '{QUEUE}'. Press CTRL+C to stop.\n")

    def callback(ch, method, properties, body):
        print("--- Message received ---")
        print(body.decode())
        print()
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=callback)
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
