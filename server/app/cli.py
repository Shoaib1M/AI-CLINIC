"""Flask CLI commands (run from server/: `flask --app wsgi <command>`)."""

import os
import random
from datetime import datetime, timedelta

import click

from .errors import ValidationError
from .extensions import db
from .models import Appointment, Patient, Prescription, User
from .services.prediction_service import prediction_record_for
from .utils.validators import validate_new_user


def _create_user(username, full_name, role, password) -> User:
    validate_new_user(username, full_name, role, password)
    user = db.session.scalar(db.select(User).filter_by(username=username))
    if user is None:
        user = User(username=username)
        db.session.add(user)
    user.full_name, user.role = full_name, role
    user.set_password(password)
    db.session.commit()
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
        """Create all database tables."""
        db.create_all()
        click.echo("Database tables created.")

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
        click.echo(f"Saved {user.role} account '{user.username}'.")

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
        try:
            doctor = _create_user("doctor1", "Dr. Evelyn Reed", "doctor", doctor_pw)
            frontdesk = _create_user("frontdesk1", "Sarah Johnson", "frontdesk", frontdesk_pw)
        except ValidationError as exc:
            raise click.ClickException(f"{exc.message} {exc.details}") from exc
        click.echo("Demo accounts ready: doctor1 (doctor), frontdesk1 (front desk).")

        if not with_appointments:
            return
        if db.session.scalar(db.select(db.func.count()).select_from(Appointment)):
            click.echo("Appointments already exist; skipping sample data.")
            return

        rng = random.Random(7)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        types = ["regular_checkup", "follow_up", "consultation", "emergency"]
        for i, (name, phone, symptoms) in enumerate(DEMO_PATIENTS):
            patient = Patient(full_name=name, phone=phone)
            offset = timedelta(days=i // 4 - 1, hours=9 + (i % 4) * 2 - now.hour)
            status = "completed" if i in (0, 3) else "cancelled" if i == 6 else "pending"
            appointment = Appointment(
                patient=patient,
                scheduled_at=now + offset,
                appointment_type=rng.choice(types),
                status=status,
                symptoms=symptoms,
                created_by=frontdesk,
            )
            appointment.prediction = prediction_record_for(symptoms)
            db.session.add(appointment)
            if status == "completed":
                disease = appointment.prediction.predicted_disease or "Under evaluation"
                db.session.add(
                    Prescription(
                        appointment=appointment,
                        doctor=doctor,
                        diagnosis=f"{disease} (clinically suspected)",
                        medications=[
                            {"name": "Paracetamol 500 mg", "dosage": "1 tablet", "instructions": "Every 6 hours if fever > 38 °C. Max 4 per day."},
                            {"name": "Oral rehydration", "dosage": None, "instructions": "Drink fluids regularly; rest for 3 days."},
                        ],
                        notes="Return if symptoms worsen or persist beyond 5 days.",
                    )
                )
        db.session.commit()
        click.echo(f"Created {len(DEMO_PATIENTS)} sample appointments.")
