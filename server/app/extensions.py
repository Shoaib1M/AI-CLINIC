"""Shared extension objects: CORS and the MongoDB connection.

The Mongo client is created once per app (PyMongo clients are thread-safe and
pool connections internally) and stored on `app.extensions`. Code reads the
database through `mongo.db`, which resolves against the current app, so tests
can run several independent apps side by side.
"""

import logging

from flask import current_app
from flask_cors import CORS
from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.server_api import ServerApi

logger = logging.getLogger(__name__)

cors = CORS()


class Mongo:
    def init_app(self, app) -> None:
        uri = app.config["MONGODB_URI"]
        if uri.startswith("mongomock://"):
            # Test-only in-memory emulator; not installed in production.
            import mongomock

            client = mongomock.MongoClient()
        else:
            client = MongoClient(
                uri,
                server_api=ServerApi("1"),  # Stable API, as with `mongosh --apiVersion 1`
                serverSelectionTimeoutMS=app.config["MONGODB_TIMEOUT_MS"],
                connectTimeoutMS=app.config["MONGODB_TIMEOUT_MS"],
                socketTimeoutMS=app.config["MONGODB_SOCKET_TIMEOUT_MS"],
                appname="ai-clinic",
            )
        app.extensions["mongo_client"] = client
        app.extensions["mongo_db"] = client[app.config["MONGODB_DB"]]

    @property
    def db(self):
        return current_app.extensions["mongo_db"]


mongo = Mongo()


def next_id(name: str) -> int:
    """Atomically allocate the next integer id for a collection.

    MongoDB's default ObjectIds would work, but short sequential ids keep the
    API unchanged (/api/appointments/13) and give readable document numbers
    (A-00013, RX-000003). `$inc` on a counter document is atomic, so two
    concurrent requests never receive the same id.
    """
    counter = mongo.db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return counter["seq"]


def ensure_indexes(db) -> None:
    """Create indexes (idempotent). Unique indexes also enforce invariants."""
    db.users.create_index("username", unique=True)
    db.patients.create_index([("full_name_lower", ASCENDING), ("phone", ASCENDING)], unique=True)
    db.patients.create_index("phone")
    db.appointments.create_index("patient_id")
    db.appointments.create_index("status")
    db.appointments.create_index("scheduled_at")
    db.appointments.create_index("prediction.predicted_disease")
    db.prescriptions.create_index("appointment_id")
