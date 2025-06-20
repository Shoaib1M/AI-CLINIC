# This is the updated and cleaned version of mcp_server.py

import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
import joblib
import os
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.types as types
from mcp.server.stdio import stdio_server

class MedicalMCPServer:
    def __init__(self):
        self.patients_db = []
        self.patient_id_counter = 1
        self.model = None
        self.mlb = None
        self.medical_df = None
        self.override_logs = []

        self.MODEL_FILE = 'disease_model.joblib'
        self.MLB_FILE = 'mlb.joblib'
        self.DATA_FILE = 'updated_synthetic_medical_dataset.csv'
        self.OVERRIDE_LOG_FILE = 'prescription_overrides.json'

        self.initialize_system()
        self.load_override_logs()

    def initialize_system(self):
        try:
            self.load_model_and_data()
        except Exception as e:
            self.initialize_mock_data()

    def initialize_mock_data(self):
        mock_data = {
            'Disease': ['Common Cold', 'Flu', 'Migraine', 'Gastritis', 'Hypertension'] * 20,
            'Symptom_1': ['Runny nose', 'Fever', 'Headache', 'Stomach pain', 'High blood pressure'] * 20,
            'Symptom_2': ['Cough', 'Body aches', 'Nausea', 'Nausea', 'Dizziness'] * 20,
            'Symptom_3': ['Sneezing', 'Fatigue', 'Light sensitivity', 'Bloating', 'Fatigue'] * 20,
            'Prescription_1': ['Rest', 'Tamiflu', 'Ibuprofen', 'Antacids', 'Lisinopril'] * 20,
            'Prescription_2': ['Fluids', 'Rest', 'Rest', 'Dietary changes', 'Lifestyle changes'] * 20,
            'Prescription_3': ['Vitamin C', 'Fluids', 'Dark room', 'Probiotics', 'Regular monitoring'] * 20
        }
        self.medical_df = pd.DataFrame(mock_data)
        self.train_model()

    def load_data(self):
        if os.path.exists(self.DATA_FILE):
            self.medical_df = pd.read_csv(self.DATA_FILE)
        else:
            raise FileNotFoundError(f"Data file not found at {self.DATA_FILE}")

    def train_model(self):
        symptom_cols = [col for col in self.medical_df.columns if col.startswith("Symptom")]
        self.medical_df["Symptoms"] = self.medical_df[symptom_cols].apply(
            lambda row: [str(s).strip() for s in row if pd.notna(s) and str(s).strip()], axis=1
        )
        valid_rows = self.medical_df["Symptoms"].apply(lambda x: len(x) > 0)
        filtered_df = self.medical_df[valid_rows]

        self.mlb = MultiLabelBinarizer()
        X = self.mlb.fit_transform(filtered_df["Symptoms"])
        y = filtered_df["Disease"]

        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X, y)

        joblib.dump(self.model, self.MODEL_FILE)
        joblib.dump(self.mlb, self.MLB_FILE)

    def load_model_and_data(self):
        self.load_data()
        if not os.path.exists(self.MODEL_FILE) or not os.path.exists(self.MLB_FILE):
            self.train_model()
        else:
            self.model = joblib.load(self.MODEL_FILE)
            self.mlb = joblib.load(self.MLB_FILE)

    def predict_disease(self, symptoms):
        if self.model is None or self.mlb is None:
            return "Unknown", "Low", []
        try:
            input_vec = self.mlb.transform([symptoms])
            prediction = self.model.predict(input_vec)[0]
            confidence = max(self.model.predict_proba(input_vec)[0])
            prescriptions = self.get_top_prescriptions(prediction)
            return prediction, f"{confidence:.1%}", prescriptions
        except:
            return "Unknown", "Error", []

    def get_top_prescriptions(self, disease):
        if self.medical_df is None:
            return []
        df = self.medical_df[self.medical_df['Disease'] == disease]
        prescriptions = df[[col for col in df.columns if col.startswith('Prescription')]].values.flatten()
        return pd.Series(prescriptions).dropna().value_counts().head(3).index.tolist()

    def create_appointment(self, name, phone, date, appointment_type, symptoms):
        disease, confidence, prescriptions = self.predict_disease(symptoms)
        patient = {
            'id': self.patient_id_counter,
            'name': name,
            'phone': phone,
            'date': date,
            'type': appointment_type,
            'symptoms': symptoms,
            'predicted_disease': disease,
            'confidence': confidence,
            'common_prescriptions': prescriptions,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        self.patients_db.append(patient)
        self.patient_id_counter += 1
        return patient

    def get_patient_by_id(self, patient_id):
        return next((p for p in self.patients_db if p['id'] == patient_id), None)

    def update_patient_status(self, patient_id, status):
        patient = self.get_patient_by_id(patient_id)
        if patient:
            patient['status'] = status
            patient['updated_at'] = datetime.now().isoformat()
            return patient
        return None

    def get_all_patients(self):
        return self.patients_db

    def get_patients_by_status(self, status):
        return [p for p in self.patients_db if p['status'] == status]

    def log_prescription_override(self, entry: dict):
        self.override_logs.append(entry)
        try:
            with open(self.OVERRIDE_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.override_logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving overrides: {e}")

    def load_override_logs(self):
        if os.path.exists(self.OVERRIDE_LOG_FILE):
            try:
                with open(self.OVERRIDE_LOG_FILE, "r", encoding="utf-8") as f:
                    self.override_logs = json.load(f)
            except Exception as e:
                print(f"Error loading overrides: {e}")

medical_server = MedicalMCPServer()
server = Server("medical-assistant")

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "create_appointment":
            patient = medical_server.create_appointment(
                name=arguments.get("name", ""),
                phone=arguments.get("phone", ""),
                date=arguments.get("date", ""),
                appointment_type=arguments.get("type", ""),
                symptoms=arguments.get("symptoms", [])
            )
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "message": "Appointment created successfully",
                "patient": patient
            }, indent=2, ensure_ascii=False))]

        elif name == "submit_final_prescription":
            patient_id = arguments.get("patient_id")
            doctor_id = arguments.get("doctor_id")
            final_prescription = arguments.get("final_prescription", [])
            patient = medical_server.get_patient_by_id(patient_id)

            if patient:
                override_entry = {
                    "doctor_id": doctor_id,
                    "patient_id": patient_id,
                    "symptoms": patient["symptoms"],
                    "predicted_disease": patient["predicted_disease"],
                    "ai_prescription": patient["common_prescriptions"],
                    "final_prescription": final_prescription,
                    "timestamp": datetime.now().isoformat()
                }
                medical_server.log_prescription_override(override_entry)
                return [TextContent(type="text", text=json.dumps({
                    "status": "success",
                    "message": "Final prescription recorded",
                    "log": override_entry
                }, indent=2, ensure_ascii=False))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "status": "error",
                    "message": f"Patient with ID {patient_id} not found"
                }, indent=2, ensure_ascii=False))]

        elif name == "generate_pdf":
            patient_name = arguments["patient_name"]
            doctor_name = arguments["doctor_name"]
            prescription = arguments["prescription"]
            diagnosis = arguments["diagnosis"]

            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=A4)
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawCentredString(300, 800, "Medical Prescription")
            pdf.setFont("Helvetica", 12)
            pdf.drawString(50, 760, f"Patient: {patient_name}")
            pdf.drawString(50, 740, f"Doctor: {doctor_name}")
            pdf.drawString(50, 720, f"Diagnosis: {diagnosis}")
            pdf.drawString(50, 700, "Prescription:")
            y = 680
            for med in prescription:
                pdf.drawString(70, y, f"- {med}")
                y -= 20
            pdf.showPage()
            pdf.save()
            buffer.seek(0)
            encoded = base64.b64encode(buffer.read()).decode("utf-8")
            return [TextContent(type="text", text=json.dumps({
                "status": "success",
                "pdf": encoded
            }, indent=2, ensure_ascii=False))]

        else:
            return [TextContent(type="text", text=json.dumps({
                "status": "error",
                "message": f"Unknown tool: {name}"
            }, indent=2, ensure_ascii=False))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({
            "status": "error",
            "message": f"Exception in {name}: {str(e)}",
            "tool": name,
            "arguments": arguments
        }, indent=2, ensure_ascii=False))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="medical-assistant",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
