import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
import joblib
import os
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

# --- Initialization ---
app = Flask(__name__)

# --- In-memory database & Globals ---
patients_db = []
patient_id_counter = 1
model = None
mlb = None
medical_df = None  # Global dataframe for prescription lookups

# --- ML Model Loading ---
MODEL_FILE = 'disease_model.joblib'
MLB_FILE = 'mlb.joblib'
DATA_FILE = 'updated_synthetic_medical_dataset.csv'


def load_data():
    """Loads the medical dataset into a global DataFrame."""
    global medical_df
    if os.path.exists(DATA_FILE):
        print("Loading data...")
        medical_df = pd.read_csv(DATA_FILE)
        print("Data loaded successfully.")
    else:
        print(f"Error: Data file not found at {DATA_FILE}. Creating mock data.")
        # Create mock data if file doesn't exist
        mock_data = {
            'Disease': ['Common Cold', 'Flu', 'Migraine', 'Gastritis', 'Hypertension'] * 20,
            'Symptom_1': ['Runny nose', 'Fever', 'Headache', 'Stomach pain', 'High blood pressure'] * 20,
            'Symptom_2': ['Cough', 'Body aches', 'Nausea', 'Nausea', 'Dizziness'] * 20,
            'Symptom_3': ['Sneezing', 'Fatigue', 'Light sensitivity', 'Bloating', 'Fatigue'] * 20,
            'Prescription_1': ['Rest', 'Tamiflu', 'Ibuprofen', 'Antacids', 'Lisinopril'] * 20,
            'Prescription_2': ['Fluids', 'Rest', 'Rest', 'Dietary changes', 'Lifestyle changes'] * 20,
            'Prescription_3': ['Vitamin C', 'Fluids', 'Dark room', 'Probiotics', 'Regular monitoring'] * 20
        }
        medical_df = pd.DataFrame(mock_data)


def train_model():
    """Trains and saves the model and multilabel binarizer."""
    print("Training model...")
    # This function uses the global medical_df loaded by load_model_and_data
    symptom_cols = [col for col in medical_df.columns if col.startswith("Symptom")]
    medical_df["Symptoms"] = medical_df[symptom_cols].apply(
        lambda row: [str(s).strip() for s in row if pd.notna(s) and str(s).strip()], axis=1
    )
    
    # Filter out rows with no symptoms
    valid_rows = medical_df["Symptoms"].apply(lambda x: len(x) > 0)
    filtered_df = medical_df[valid_rows]

    local_mlb = MultiLabelBinarizer()
    X = local_mlb.fit_transform(filtered_df["Symptoms"])
    y = filtered_df["Disease"]

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    joblib.dump(model, MODEL_FILE)
    joblib.dump(local_mlb, MLB_FILE)
    print("Model trained and saved.")
    return model, local_mlb


def load_model_and_data():
    """Loads the data, and then loads the model or trains if not found."""
    global model, mlb
    load_data()  # Load data first
    if not os.path.exists(MODEL_FILE) or not os.path.exists(MLB_FILE):
        print("Model files not found. Training new model...")
        model, mlb = train_model()
    else:
        try:
            model = joblib.load(MODEL_FILE)
            mlb = joblib.load(MLB_FILE)
            print("Model and MLB loaded successfully.")
        except Exception as e:
            print(f"Error loading model or MLB: {e}. Attempting to retrain.")
            model, mlb = train_model()


# Load model and data at application startup
with app.app_context():
    load_model_and_data()


def get_top_prescriptions(disease):
    """Finds the top 3 most common prescriptions for a given disease."""
    # This check is important if the data file failed to load
    if medical_df is None or medical_df.empty:
        return ["Prescription data unavailable."]

    # Assumes prescription columns are named like 'Prescription_1', 'Prescription_2' etc.
    prescription_cols = [col for col in medical_df.columns if col.startswith("Prescription")]
    if not prescription_cols:
        return ["No prescription columns in dataset."]

    disease_df = medical_df[medical_df['Disease'] == disease]
    if disease_df.empty:
        return ["N/A"]

    prescriptions = disease_df[prescription_cols].values.flatten()
    prescriptions = [p for p in prescriptions if pd.notna(p) and str(p).strip()]

    if not prescriptions:
        return ["No prescriptions listed for this disease."]

    prescription_counts = pd.Series(prescriptions).value_counts()
    return prescription_counts.head(3).index.tolist()


def predict_disease(symptoms):
    """Predicts disease, confidence, and top prescriptions."""
    if not isinstance(symptoms, list):
        return "Invalid input", "N/A", []

    try:
        input_vec = mlb.transform([symptoms])
        prediction = model.predict(input_vec)[0]
        prediction_proba = model.predict_proba(input_vec)
        confidence = max(prediction_proba[0])

        # NEW: Get top prescriptions for the predicted disease
        top_prescriptions = get_top_prescriptions(prediction)

        return prediction, f"{confidence:.2%}", top_prescriptions
    except Exception as e:
        if hasattr(mlb, 'classes_') and mlb.classes_ is not None:
            unseen_symptoms = [s for s in symptoms if s not in mlb.classes_]
            if unseen_symptoms:
                return "Cannot predict", f"Unseen: {', '.join(unseen_symptoms)}", []
        print(f"Prediction error: {e}")
        return "Prediction Error", "N/A", []


def generate_prescription_pdf(patient_name, doctor_name, prescription, diagnosis):
    """Generate a PDF prescription and return it as bytes."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Header
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(width/2, height-50, "MEDICAL PRESCRIPTION")
    
    # Date
    pdf.setFont("Helvetica", 12)
    current_date = datetime.now().strftime("%B %d, %Y")
    pdf.drawString(50, height-100, f"Date: {current_date}")
    
    # Patient Info
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height-140, "Patient Information:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(70, height-160, f"Name: {patient_name}")
    
    # Doctor Info
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height-200, "Prescribing Physician:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(70, height-220, f"Dr. {doctor_name}")
    
    # Diagnosis
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height-260, "Diagnosis:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(70, height-280, diagnosis)
    
    # Prescription
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height-320, "Prescription:")
    pdf.setFont("Helvetica", 12)
    
    y_position = height-350
    for i, medication in enumerate(prescription, 1):
        pdf.drawString(70, y_position, f"{i}. {medication}")
        y_position -= 25
    
    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(50, 50, "This prescription is generated electronically and is valid.")
    pdf.drawString(50, 35, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/frontdesk')
def frontdesk():
    return render_template('frontdesk.html')


@app.route('/doctor')
def doctor():
    return render_template('doctor.html')


@app.route('/api/appointments', methods=['POST', 'GET'])
def manage_appointments():
    """API endpoint to manage appointments."""
    global patient_id_counter

    if request.method == 'POST':
        data = request.json
        symptoms = [s.strip() for s in data.get('symptoms', '').split(',') if s.strip()]

        # UPDATED: Now receives three values
        predicted_disease, confidence, prescriptions = predict_disease(symptoms)

        new_patient = {
            'id': patient_id_counter,
            'name': data.get('name'),
            'phone': data.get('phone'),
            'date': data.get('date'),
            'type': data.get('type'),
            'symptoms': symptoms,
            'predicted_disease': predicted_disease,
            'confidence': confidence,
            'common_prescriptions': prescriptions,  # ADDED: New field for prescriptions
            'status': 'pending'
        }
        patients_db.append(new_patient)
        patient_id_counter += 1
        return jsonify({'message': 'Appointment created successfully', 'patient': new_patient}), 201

    elif request.method == 'GET':
        return jsonify(patients_db)


@app.route('/api/appointments/<int:patient_id>', methods=['PUT'])
def update_appointment_status(patient_id):
    """API endpoint to update appointment status."""
    data = request.json
    status = data.get('status')
    patient = next((p for p in patients_db if p['id'] == patient_id), None)
    if patient:
        patient['status'] = status
        return jsonify({'message': 'Appointment status updated successfully', 'patient': patient}), 200
    return jsonify({'message': 'Patient not found'}), 404


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """Generate and download a PDF prescription."""
    try:
        data = request.json
        
        # Extract data from request
        patient_name = data.get('patient_name', 'Unknown Patient')
        doctor_name = data.get('doctor_name', 'Unknown Doctor')
        prescription = data.get('prescription', [])
        diagnosis = data.get('diagnosis', 'Unknown Diagnosis')
        
        # Validate required fields
        if not patient_name or not doctor_name:
            return jsonify({'error': 'Patient name and doctor name are required'}), 400
        
        # Generate PDF
        pdf_buffer = generate_prescription_pdf(patient_name, doctor_name, prescription, diagnosis)
        
        # Set proper headers for PDF download
        filename = f'prescription_{patient_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        # Return PDF as downloadable file with proper headers
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500


@app.route('/api/generate-pdf-base64', methods=['POST'])
def generate_pdf_base64():
    """Generate PDF and return as base64 string for web display."""
    try:
        data = request.json
        
        # Extract data from request
        patient_name = data.get('patient_name', 'Unknown Patient')
        doctor_name = data.get('doctor_name', 'Unknown Doctor')
        prescription = data.get('prescription', [])
        diagnosis = data.get('diagnosis', 'Unknown Diagnosis')
        
        # Validate required fields
        if not patient_name or not doctor_name:
            return jsonify({'error': 'Patient name and doctor name are required'}), 400
        
        # Generate PDF
        pdf_buffer = generate_prescription_pdf(patient_name, doctor_name, prescription, diagnosis)
        
        # Convert to base64
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            'status': 'success',
            'pdf_base64': pdf_base64,
            'filename': f'prescription_{patient_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.pdf'
        })
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500


@app.route('/api/generate-pdf/<int:patient_id>', methods=['GET'])
def generate_pdf_for_patient(patient_id):
    """Generate PDF for a specific patient by ID."""
    try:
        # Find patient
        patient = next((p for p in patients_db if p['id'] == patient_id), None)
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Use patient data to generate PDF
        pdf_buffer = generate_prescription_pdf(
            patient_name=patient['name'],
            doctor_name='Dr. System',  # You can modify this
            prescription=patient.get('common_prescriptions', []),
            diagnosis=patient.get('predicted_disease', 'Unknown')
        )
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'prescription_{patient["name"].replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.pdf'
        )
        
    except Exception as e:
        print(f"Error generating PDF for patient {patient_id}: {e}")
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500


@app.route('/test-pdf')
def test_pdf():
    """Test route to generate a sample PDF."""
    try:
        pdf_buffer = generate_prescription_pdf(
            patient_name="John Doe",
            doctor_name="Dr. Smith",
            prescription=["Paracetamol 500mg - Take 1 tablet every 6 hours", "Rest for 3 days", "Drink plenty of fluids"],
            diagnosis="Common Cold"
        )
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='test_prescription.pdf'
        )
    except Exception as e:
        return f"Error generating test PDF: {e}", 500


if __name__ == '__main__':
    app.run(debug=True)
@app.route('/generate-pdf', methods=['POST'])
def generate_pdf_route():
    """Direct route for PDF generation."""
    return generate_pdf()  # Use your existing generate_pdf function
