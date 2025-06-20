# HealthCare Pro - Modern Healthcare Management System

HealthCare Pro is a full-stack web application for patient and appointment management, including AI-driven disease prediction and PDF prescription generation. It offers distinct portals for front-desk staff and doctors.


## Features

* **User Authentication:** Secure login for Front Desk and Doctor roles.
* **Front Desk Portal:** Book appointments, capture symptoms, get AI-predicted disease diagnoses, and view appointment lists.
* **Doctor Portal:** View patient details, predicted diseases, manage appointment statuses, and generate customizable PDF prescriptions with pre-filled details.
* **Responsive Design:** Optimized for all devices.
* **PDF Generation:** Backend Flask endpoint for prescription PDFs.
* **In-Memory Database:** Simple data storage for demonstration.

## Technologies Used

**Backend:**
* **Flask:** Web framework.
* **Scikit-learn:** ML model for disease prediction.
* **Pandas:** Data manipulation.
* **Joblib:** Model persistence.
* **ReportLab:** PDF generation.

**Frontend:**
* **HTML5, CSS3, JavaScript (ES6+):** For the web interface.

**Other:**
* `updated_synthetic_medical_dataset.csv`: Medical dataset for training.
* `requirements.txt`: Python dependencies.

## Project Structure

```
.
├── app.py                     # Flask backend
├── requirements.txt           # Python dependencies
├── updated_synthetic_medical_dataset.csv # Medical dataset
├── static/
│   ├── style.css              # CSS styles
│   └── script.js              # JavaScript logic
├── templates/
│   ├── index.html             # Home page
│   ├── frontdesk.html         # Front Desk portal
│   └── doctor.html            # Doctor portal
└── claude_desktop_config.json.json # (Local development config)
```

## Setup and Installation

### Prerequisites

* Python 3.8+
* `pip`

### Backend Setup

1.  **Clone the repository:** `git clone <your-repository-url> && cd healthcare-pro`
2.  **Create virtual environment:** `python -m venv venv`
3.  **Activate virtual environment:**
    * Windows: `.\venv\Scripts\activate`
    * macOS/Linux: `source venv/bin/activate`
4.  **Install packages:** `pip install -r requirements.txt`

### Required Libraries

The `requirements.txt` file ensures that all necessary Python libraries are installed. These include:
* `flask==2.3.3`
* `pandas==2.0.3`
* `scikit-learn==1.3.0`
* `joblib==1.3.2`
* `mcp==1.0.0`
* `asyncio`
* `reportlab` (for PDF generation, indirectly installed via other dependencies or needs separate mention if not implicitly covered)

### Running the Application

1.  **From project root with venv activated, run:** `python app.py`
2.  **Navigate to:** `http://127.0.0.1:5000/` in your browser.

## Usage

* **Home Page:** Links to Doctor and Front Desk portals.
* **Front Desk System:** Login, book appointments with AI prediction, view appointments.
* **Doctor Dashboard:** Login, view patient list, manage status, generate customizable PDF prescriptions.

## Demo Credentials

* **Doctor Portal:** `doctor1` / `password`
* **Front Desk Portal:** `frontdesk1` / `password`

## Contributing

1.  Fork, branch (`feature/your-feature`), make changes.
2.  Commit (`git commit -m 'feat: New feature'`).
3.  Push (`git push origin feature/your-feature`).
4.  Open a Pull Request.

