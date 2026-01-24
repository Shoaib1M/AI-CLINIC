# 🏥 HealthCare Pro — AI-Assisted Healthcare Management System

HealthCare Pro is a full-stack web application for appointment and patient management, featuring **AI-driven disease prediction** and **PDF prescription generation**.  
It provides separate portals for **Front Desk staff** and **Doctors** to simulate a real clinic workflow.

---

## Features

 **Role-Based Portals**
- Front Desk Portal (Appointment booking + symptom input)
- Doctor Portal (Patient dashboard + status updates)

 **AI Disease Prediction**
- Symptom-based disease prediction using Machine Learning
- Shows predicted disease + confidence score

 **Doctor Dashboard**
- View all patient bookings
- Search patients by name / symptoms / predicted disease
- Update appointment status (**Pending / Completed / Cancelled**)

 **PDF Prescription Generator**
- Editable prescription modal (doctor can modify medicines)
- Downloadable prescription PDF generated from backend

 **Responsive UI**
- Works smoothly on desktop and mobile

 **In-Memory Storage**
- Uses an in-memory database (`patients_db`) for demo purposes  
  *(data resets when server restarts)*

---

## 🧠 ML Model Performance

- **Model:** RandomForestClassifier  
- **Encoding:** MultiLabelBinarizer (multi-symptom feature encoding)
- **Test Accuracy:** **97.01%**

---

## 🛠️ Tech Stack

### Backend
- **Flask** (API + routing)
- **Scikit-learn** (ML model)
- **Pandas** (dataset + preprocessing)
- **Joblib** (model saving/loading)
- **ReportLab** (PDF generation)

### Frontend
- **HTML5**
- **CSS3**
- **JavaScript (ES6+)**

---

## 📁 Project Structure

```bash
.
├── app.py
├── requirements.txt
├── runtime.txt
├── updated_synthetic_medical_dataset.csv
├── static/
│   ├── style.css
│   └── script.js
├── templates/
│   ├── index.html
│   ├── frontdesk.html
│   └── doctor.html
└── README.md
