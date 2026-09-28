"""Flask CLI commands (run from server/: `flask --app wsgi <command>`)."""

import os
import random
from datetime import datetime, timedelta

import click

from .errors import ValidationError
from .extensions import ensure_indexes, mongo, next_id
from .models import User, utcnow
from .services.prediction_service import prediction_record_for
from .utils.validators import validate_new_user


def _create_user(username, full_name, role, password) -> dict:
    """Create the account, or update name/role/password if the username exists."""
    validate_new_user(username, full_name, role, password)
    now = utcnow()
    fields = {"full_name": full_name, "role": role, "password_hash": User.hash_password(password), "updated_at": now}
    existing = mongo.db.users.find_one({"username": username})
    if existing:
        mongo.db.users.update_one({"_id": existing["_id"]}, {"$set": fields})
        return {**existing, **fields}
    user = {"_id": next_id("users"), "username": username, "is_active": True, "created_at": now, **fields}
    mongo.db.users.insert_one(user)
    return user


# Fictional patients and realistic symptom combinations for the demo seed.
DEMO_PATIENTS = [
    ("Aarav Mehta", "+91 98100 11201", ["fever", "cough", "fatigue", "body ache", "loss of appetite"]),
    ("Priya Nair", "+91 98100 11202", ["sneezing", "runny nose", "itchy eyes", "congestion"]),
    ("Rohan Das", "+91 98100 11203", ["headache", "nausea", "blurred vision", "dizziness"]),
    ("Meera Iyer", "+91 98100 11204", ["fever", "chills", "vomiting", "nausea", "body ache"]),
    ("Kabir Singh", "+91 98100 11205", ["cough", "sore throat", "runny nose", "sneezing", "congestion"]),
    ("Ananya Rao", "+91 98100 11206", ["fever", "rash", "joint pain", "headache", "fatigue"]),
    ("Vikram Patel", "+91 98100 11207", ["diarrhea", "vomiting", "nausea", "fatigue"]),
    ("Sara Thomas", "+91 98100 11208", ["fever", "shortness of breath", "chest pain", "cough", "fatigue"]),
    ("Ishaan Gupta", "+91 98100 11209", ["headache", "congestion", "fever", "fatigue"]),
    ("Neha Kulkarni", "+91 98100 11210", ["fever", "headache", "body ache", "fatigue", "chills"]),
    ("Arjun Menon", "+91 98100 11211", ["cough", "palpitations", "fatigue"]),
    ("Divya Sharma", "+91 98100 11212", ["back pain", "insomnia"]),
]


def register(app) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Create the MongoDB indexes (safe to run repeatedly)."""
        ensure_indexes(mongo.db)
        click.echo(f"Indexes ready in database '{app.config['MONGODB_DB']}'.")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.option("--role", type=click.Choice(["doctor", "frontdesk"]), required=True)
    @click.option("--full-name", required=True, help='Display name, e.g. "Dr. Evelyn Reed"')
    @click.password_option()
    def create_user(username, role, full_name, password):
        """Create or update a staff account (password is prompted, never stored in plain text)."""
        try:
            user = _create_user(username, full_name, role, password)
        except ValidationError as exc:
            raise click.ClickException(f"{exc.message} {exc.details}") from exc
        click.echo(f"Saved {user['role']} account '{user['username']}'.")

    @app.cli.command("seed-demo")
    @click.option("--with-appointments", is_flag=True, help="Also create sample patients and appointments.")
    def seed_demo(with_appointments):
        """Create demo accounts using passwords from DEMO_DOCTOR_PASSWORD / DEMO_FRONTDESK_PASSWORD."""
        doctor_pw = os.getenv("DEMO_DOCTOR_PASSWORD")
        frontdesk_pw = os.getenv("DEMO_FRONTDESK_PASSWORD")
        if not doctor_pw or not frontdesk_pw:
            raise click.ClickException(
                "Set DEMO_DOCTOR_PASSWORD and DEMO_FRONTDESK_PASSWORD (see .env.example) before seeding."
            )
        ensure_indexes(mongo.db)
        try:
            doctor = _create_user("doctor1", "Dr. Evelyn Reed", "doctor", doctor_pw)
            frontdesk = _create_user("frontdesk1", "Sarah Johnson", "frontdesk", frontdesk_pw)
        except ValidationError as exc:
            raise click.ClickException(f"{exc.message} {exc.details}") from exc
        click.echo("Demo accounts ready: doctor1 (doctor), frontdesk1 (front desk).")

        if not with_appointments:
            return
        if mongo.db.appointments.count_documents({}, limit=1):
            click.echo("Appointments already exist; skipping sample data.")
            return

        rng = random.Random(7)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        types = ["regular_checkup", "follow_up", "consultation", "emergency"]
        for i, (name, phone, symptoms) in enumerate(DEMO_PATIENTS):
            created = utcnow()
            patient = {
                "_id": next_id("patients"),
                "full_name": name,
                "full_name_lower": name.lower(),
                "phone": phone,
                "created_at": created,
                "updated_at": created,
            }
            mongo.db.patients.insert_one(patient)
            status = "completed" if i in (0, 3) else "cancelled" if i == 6 else "pending"
            prediction = prediction_record_for(symptoms)
            appointment = {
                "_id": next_id("appointments"),
                "patient_id": patient["_id"],
                "patient_name": name,
                "patient_name_lower": name.lower(),
                "patient_phone": phone,
                "scheduled_at": now + timedelta(days=i // 4 - 1, hours=9 + (i % 4) * 2 - now.hour),
                "appointment_type": rng.choice(types),
                "status": status,
                "symptoms": symptoms,
                "prediction": prediction,
                "prescription_count": 1 if status == "completed" else 0,
                "created_by_id": frontdesk["_id"],
                "created_at": created,
                "updated_at": created,
            }
            mongo.db.appointments.insert_one(appointment)
            if status == "completed":
                disease = prediction.get("predicted_disease") or "Under evaluation"
                mongo.db.prescriptions.insert_one(
                    {
                        "_id": next_id("prescriptions"),
                        "appointment_id": appointment["_id"],
                        "doctor_id": doctor["_id"],
                        "diagnosis": f"{disease} (clinically suspected)",
                        "medications": [
                            {"name": "Paracetamol 500 mg", "dosage": "1 tablet", "instructions": "Every 6 hours if fever > 38 °C. Max 4 per day."},
                            {"name": "Oral rehydration", "dosage": None, "instructions": "Drink fluids regularly; rest for 3 days."},
                        ],
                        "notes": "Return if symptoms worsen or persist beyond 5 days.",
                        "created_at": created,
                        "updated_at": created,
                    }
                )
        click.echo(f"Created {len(DEMO_PATIENTS)} sample appointments.")
