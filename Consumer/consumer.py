from kafka import KafkaConsumer
import json, os
from pymongo import MongoClient
from datetime import datetime

KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP", 
    "uni-it-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
)
TOPIC = "student-events"

# Connessione MongoDB
MONGO_URI = os.getenv(
    "MONGO_URI", 
    "mongodb://user:password@mongo-mongodb.mongo.svc.cluster.local:27017/student_events"
)
client = MongoClient(MONGO_URI)
db = client.student_events
collection = db.events

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    auto_offset_reset='earliest',
    group_id='db-consumer-group',
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

print("Consumer avviato, in ascolto su topic:", TOPIC)
for message in consumer:
    event = message.value
    # aggiungo timestamp locale per tracciamento ingest
    event["_ingest_ts"] = datetime.utcnow()
    collection.insert_one(event)
    print(f"Evento salvato su DB: {event}", flush=True)
