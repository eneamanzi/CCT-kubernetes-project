from flask import Flask, request, jsonify
from kafka import KafkaProducer
import json, os

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "uni-it-cluster-kafka-bootstrap.kafka:9092")
TOPIC = "student-events"

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

app = Flask(__name__)

@app.route("/event", methods=["POST"])
def handle_event():
    data = request.json
    producer.send(TOPIC, value=data)
    producer.flush()
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
