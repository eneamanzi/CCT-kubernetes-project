from flask import Flask, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

MONGO_URI = "mongodb://user:password@mongo-mongodb.mongo.svc.cluster.local:27017/student_events"
client = MongoClient(MONGO_URI)
db = client.student_events
collection = db.events

@app.route("/metrics/logins", methods=["GET"])
def logins():
    count = collection.count_documents({"type": "login"})
    return jsonify({"total_logins": count})

@app.route("/metrics/quiz", methods=["GET"])
def quiz():
    pipeline = [
        {"$match": {"type": "quiz_submission"}},
        {"$group": {"_id": "$quiz_id", "average_score": {"$avg": "$score"}}}
    ]
    results = list(collection.aggregate(pipeline))
    return jsonify(results)

@app.route("/metrics/downloads", methods=["GET"])
def downloads():
    pipeline = [
        {"$match": {"type": "download_materiale"}},
        {"$group": {"_id": "$materiale_id", "downloads": {"$sum": 1}}}
    ]
    results = list(collection.aggregate(pipeline))
    return jsonify(results)

@app.route("/metrics/exams", methods=["GET"])
def exams():
    pipeline = [
        {"$match": {"type": "prenotazione_esame"}},
        {"$group": {"_id": "$esame_id", "prenotazioni": {"$sum": 1}}}
    ]
    results = list(collection.aggregate(pipeline))
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
