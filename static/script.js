document.addEventListener('DOMContentLoaded', function() {
    // --- Global State ---
    const users = {
        doctor1: { password: 'password', role: 'doctor', name: 'Dr. Evelyn Reed' },
        frontdesk1: { password: 'password', role: 'frontdesk', name: 'Sarah Johnson' }
    };
    let selectedPatientForPDF = null;

    let currentUser = null;
    let appointments = []; // This will be fetched from the server


    // --- Page Initializers ---
    if (document.getElementById('main-content')) {
        initHomePage();
    } else if (document.getElementById('doctor-login')) {
        initDoctorPage();
    } else if (document.getElementById('frontdesk-login')) {
        initFrontDeskPage();
    }
    // --- PDF Modal Logic ---

// Make generatePDF global so it works from inline HTML
window.generatePDF = function(patient) {
    selectedPatientForPDF = patient;
    document.getElementById('pdf-modal').style.display = 'flex';
    document.getElementById('modal-prescription').value = (patient.common_prescriptions || []).join(', ');
};

const pdfForm = document.getElementById('pdf-form');
if (pdfForm) {
    pdfForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const prescriptionStr = document.getElementById('modal-prescription').value;
        const prescriptionArr = prescriptionStr.split(',').map(s => s.trim()).filter(Boolean);

        fetch("/api/generate-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                patient_name: selectedPatientForPDF.name,
                doctor_name: currentUser && currentUser.name ? currentUser.name : "Doctor",
                prescription: prescriptionArr,
                diagnosis: selectedPatientForPDF.predicted_disease || ""
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to generate PDF");
            return res.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "prescription.pdf";
            a.click();
            closePDFModal();
        })
        .catch(() => alert("Failed to generate PDF. Please try again."));
    });
}

const closeBtn = document.getElementById('close-pdf-modal');
if (closeBtn) {
    closeBtn.addEventListener('click', closePDFModal);
}

function closePDFModal() {
    document.getElementById('pdf-modal').style.display = 'none';
    selectedPatientForPDF = null;
}

    // --- Home Page Logic ---
    function initHomePage() {
        setupMobileMenu();
    }

    // --- Doctor Page Logic ---
    function initDoctorPage() {
        const doctorLoginForm = document.getElementById('doctor-login-form');
        if (doctorLoginForm) {
            doctorLoginForm.addEventListener('submit', handleDoctorLogin);
        }
    }

    function handleDoctorLogin(e) {
        e.preventDefault();
        const username = document.getElementById('doctor-username').value;
        const password = document.getElementById('doctor-password').value;
        if (authenticateUser(username, password, 'doctor')) {
            currentUser = { username, role: 'doctor', name: users[username].name };
            showDoctorDashboard();
        } else {
            showError('Invalid credentials. Try: doctor1 / password', 'doctor-login-form');
        }
    }

    function showDoctorDashboard() {
        document.getElementById('doctor-login').style.display = 'none';
        document.getElementById('doctor-dashboard').style.display = 'block';
        document.getElementById('doctor-name').textContent = currentUser.name;
        fetchAppointmentsForDoctor();
        // Add event listener for patient search
        document.getElementById('patient-search').addEventListener('input', filterAppointments);
    }

    async function fetchAppointmentsForDoctor() {
        try {
            const response = await fetch('/api/appointments');
            if (!response.ok) {
                throw new Error('Failed to fetch appointments for doctor.');
            }
            appointments = await response.json();
            document.getElementById('total-patients').textContent = appointments.length;
            renderPatientList(); // Render all appointments initially
        } catch (error) {
            console.error('Error fetching appointments for doctor:', error);
            showError('Could not load appointments.', 'doctor-dashboard');
        }
    }

    function renderPatientList() {
        const patientListDiv = document.getElementById('patient-list');
        patientListDiv.innerHTML = ''; // Clear existing list

        if (appointments.length === 0) {
            patientListDiv.innerHTML = '<p class="no-patients-message">No patients booked yet.</p>';
            return;
        }

       // ...existing code...
appointments.forEach(patient => {
    const patientCard = document.createElement('div');
    patientCard.className = 'patient-card';
    patientCard.innerHTML = `
        <div class="patient-info">
            <h3>${patient.name} (${patient.id})</h3>
            <p>Phone: ${patient.phone}</p>
            <p>Date: ${patient.date}</p>
            <p>Type: ${patient.type}</p>
            <p>Symptoms: ${patient.symptoms.join(', ') || 'N/A'}</p>
            <div class="status-indicator status-${patient.status.toLowerCase()}">
    Status: ${patient.status.charAt(0).toUpperCase() + patient.status.slice(1)}
</div>
            <div style="color: rgba(255, 255, 255, 0.8); font-size: 0.9rem; margin-top: 5px;">
                Predicted Disease: <strong>${patient.predicted_disease || 'N/A'}</strong>
            </div>
            <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.85rem;">Confidence: ${patient.confidence || 'N/A'}</div>
            <div class="common-prescriptions" style="margin-top: 10px; padding: 10px; background-color: rgba(0,0,0,0.2); border-radius: 8px;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: rgba(255, 255, 255, 0.9);">Common Prescriptions:</p>
                <ul style="list-style-type: disc; padding-left: 20px; margin: 0; color: rgba(255, 255, 255, 0.8);">
                    ${(patient.common_prescriptions && patient.common_prescriptions.length > 0)
                        ? patient.common_prescriptions.map(p => `<li>${p}</li>`).join('')
                        : '<li>N/A</li>'
                    }
                </ul>
            </div>
            
        </div>
        <div class="patient-actions">
            <button class="btn btn-secondary" onclick="updateAppointmentStatus(${patient.id}, 'completed')">Mark Completed</button>
            <button class="btn btn-secondary" onclick="updateAppointmentStatus(${patient.id}, 'cancelled')">Mark Cancelled</button>
            <button class="btn btn-primary" onclick='generatePDF(${JSON.stringify(patient)})'>Generate PDF</button>
        </div>
    `;
    patientListDiv.appendChild(patientCard);
});
// ...existing code...
    }

    // Filter appointments for doctor dashboard
    function filterAppointments() {
        const searchTerm = document.getElementById('patient-search').value.toLowerCase();
        const filtered = appointments.filter(patient =>
            patient.name.toLowerCase().includes(searchTerm) ||
            (patient.predicted_disease && patient.predicted_disease.toLowerCase().includes(searchTerm)) ||
            (patient.symptoms && patient.symptoms.some(symptom => symptom.toLowerCase().includes(searchTerm)))
        );
        renderFilteredPatientList(filtered);
    }

    function renderFilteredPatientList(filteredAppointments) {
        const patientListDiv = document.getElementById('patient-list');
        patientListDiv.innerHTML = ''; // Clear existing list

        if (filteredAppointments.length === 0) {
            patientListDiv.innerHTML = '<p class="no-patients-message">No matching patients found.</p>';
            return;
        }

        filteredAppointments.forEach(patient => {
            const patientCard = document.createElement('div');
            patientCard.className = 'patient-card';
            // MODIFIED: Added prescription display logic
            patientCard.innerHTML = `
                <div class="patient-info">
                    <h3>${patient.name} (${patient.id})</h3>
                    <p style="font-family: Caprasimo;">Phone: ${patient.phone}</p>
                    <p style="font-family: Caprasimo;">Date: ${patient.date}</p>
                    <p style="font-family: Caprasimo;">Type: ${patient.type}</p>
                    <p style="font-family: Caprasimo;">Symptoms: ${patient.symptoms.join(', ') || 'N/A'}</p>
                    <div class="status-indicator status-${patient.status.toLowerCase()}" style="font-family: Caprasimo;">
    Status: ${patient.status.charAt(0).toUpperCase() + patient.status.slice(1)}
</div>
                    <div style="color: rgba(255, 255, 255, 0.8); font-size: 0.9rem; margin-top: 5px;">
                        Predicted Disease: <strong>${patient.predicted_disease || 'N/A'}</strong>
                    </div>
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.85rem;">Confidence: ${patient.confidence || 'N/A'}</div>

                    <div class="common-prescriptions" style="margin-top: 10px; padding: 10px; background-color: rgba(0,0,0,0.2); border-radius: 8px;">
                        <p style="margin: 0 0 5px 0; font-weight: bold; color: rgba(255, 255, 255, 0.9);">Common Prescriptions:</p>
                        <ul style="list-style-type: disc; padding-left: 20px; margin: 0; color: rgba(255, 255, 255, 0.8);">
                            ${(patient.common_prescriptions && patient.common_prescriptions.length > 0)
                                ? patient.common_prescriptions.map(p => `<li>${p}</li>`).join('')
                                : '<li>N/A</li>'
                            }
                        </ul>
                    </div>

                    
                </div>
                <div class="patient-actions">
                    <button class="btn btn-secondary" onclick="updateAppointmentStatus(${patient.id}, 'completed')">Mark Completed</button>
                    <button class="btn btn-secondary" onclick="updateAppointmentStatus(${patient.id}, 'cancelled')">Mark Cancelled</button>
                    <button class="btn btn-primary" onclick='generatePDF(${JSON.stringify(patient)})'>Generate PDF</button>
                </div>
            `;
            patientListDiv.appendChild(patientCard);
        });
    }


    // Make updateAppointmentStatus global to be accessible from onclick in HTML
    window.updateAppointmentStatus = async function(patientId, status) {
        try {
            const response = await fetch(`/api/appointments/${patientId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: status })
            });
            const data = await response.json();
            if (response.ok) {
                showSuccessMessage(data.message);
                fetchAppointmentsForDoctor(); // Refresh the list
            } else {
                showError(data.message || 'Failed to update status', 'doctor-dashboard');
            }
        } catch (error) {
            console.error('Error updating appointment status:', error);
            showError('Network error or server unavailable.', 'doctor-dashboard');
        }
    };

    // Make logout global
    window.logout = function() {
        currentUser = null;
        if (document.getElementById('doctor-dashboard')) {
            document.getElementById('doctor-dashboard').style.display = 'none';
            document.getElementById('doctor-login').style.display = 'block';
        } else if (document.getElementById('frontdesk-dashboard')) {
            document.getElementById('frontdesk-dashboard').style.display = 'none';
            document.getElementById('frontdesk-login').style.display = 'block';
        }
        showSuccessMessage('Logged out successfully.');
        window.location.href = '/'; // Redirect to home page
    };


    // --- Front Desk Page Logic (ENTIRELY UNCHANGED) ---
    function initFrontDeskPage() {
        const frontdeskLoginForm = document.getElementById('frontdesk-login-form');
        if (frontdeskLoginForm) {
            frontdeskLoginForm.addEventListener('submit', handleFrontdeskLogin);
        }

        const newAppointmentForm = document.getElementById('new-appointment-form');
        if (newAppointmentForm) {
            newAppointmentForm.addEventListener('submit', bookAppointment);
        }

        document.getElementById('show-appointment-form-btn').addEventListener('click', showAppointmentForm);
        document.getElementById('fetch-appointments-btn').addEventListener('click', fetchAppointmentsForFrontDesk);

        fetchAppointmentsForFrontDesk();
    }

    function handleFrontdeskLogin(e) {
        e.preventDefault();
        const username = document.getElementById('frontdesk-username').value;
        const password = document.getElementById('frontdesk-password').value;
        if (authenticateUser(username, password, 'frontdesk')) {
            currentUser = { username, role: 'frontdesk', name: users[username].name };
            showFrontDeskDashboard();
        } else {
            showError('Invalid credentials. Try: frontdesk1 / password', 'frontdesk-login-form');
        }
    }

    function showFrontDeskDashboard() {
        document.getElementById('frontdesk-login').style.display = 'none';
        document.getElementById('frontdesk-dashboard').style.display = 'block';
        document.getElementById('frontdesk-name').textContent = currentUser.name;
    }

    async function fetchAppointmentsForFrontDesk() {
        try {
            const response = await fetch('/api/appointments');
            if (!response.ok) {
                throw new Error('Failed to fetch appointments for front desk.');
            }
            appointments = await response.json();
            renderAppointmentList();
            document.getElementById('total-appointments').textContent = appointments.length;
        } catch (error) {
            console.error('Error fetching appointments for front desk:', error);
            showError('Could not load appointments.', 'frontdesk-dashboard');
        }
    }

    function renderAppointmentList() {
        const appointmentListDiv = document.getElementById('appointment-list');
        appointmentListDiv.innerHTML = '';

        if (appointments.length === 0) {
            appointmentListDiv.innerHTML = '<p class="no-appointments-message">No appointments booked yet.</p>';
            return;
        }

        appointments.forEach(patient => {
            const patientCard = document.createElement('div');
            patientCard.className = 'patient-card';
            patientCard.innerHTML = `
                <div class="patient-info">
                    <h3>${patient.name} (${patient.id})</h3>
                    <p>Phone: ${patient.phone}</p>
                    <p>Date: ${patient.date}</p>
                    <p>Type: ${patient.type}</p>
                    <p>Symptoms: ${patient.symptoms.join(', ') || 'N/A'}</p>
                    <div style="color: rgba(255, 255, 255, 0.8); font-size: 0.9rem; margin-top: 5px;">
                        Predicted Disease: <strong>${patient.predicted_disease || 'N/A'}</strong>
                    </div>
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.85rem;">Confidence: ${patient.confidence || 'N/A'}</div>
                    <div class="status-indicator status-${patient.status.toLowerCase()}">${patient.status}</div>
                </div>
            `;
            appointmentListDiv.appendChild(patientCard);
        });
    }

    async function bookAppointment(e) {
        e.preventDefault();
        const name = document.getElementById('patient-name').value;
        const phone = document.getElementById('patient-phone').value;
        const date = document.getElementById('appointment-date').value;
        const type = document.getElementById('appointment-type').value;
        const symptoms = document.getElementById('patient-symptoms').value;

        if (!name || !phone || !date || !type || !symptoms) {
            showError('Please fill in all required fields.', 'new-appointment-form');
            return;
        }

        const appointmentData = { name, phone, date, type, symptoms };

        try {
            const response = await fetch('/api/appointments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(appointmentData),
            });

            if (!response.ok) {
                let errorMessage = 'Failed to book appointment.';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.message || errorMessage;
                } catch (jsonError) {
                    errorMessage = `Server error: ${response.status} ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            const result = await response.json();
            if (result && result.patient) {
                appointments.push(result.patient);
                renderAppointmentList();
                document.getElementById('total-appointments').textContent = appointments.length;
                hideAppointmentForm();
                e.target.reset();
                showSuccessMessage('Appointment booked successfully!');
            } else {
                throw new Error('Invalid response from server: Missing patient data.');
            }

        } catch (error) {
            console.error('Booking Error:', error);
            showError(error.message, 'new-appointment-form');
        }
    };

    function showAppointmentForm() {
        document.getElementById('new-appointment-form-container').style.display = 'block';
    }

    window.hideAppointmentForm = function() {
        document.getElementById('new-appointment-form-container').style.display = 'none';
    };

    // --- Utility Functions (UNCHANGED) ---
    function authenticateUser(username, password, role) {
        const user = users[username];
        return user && user.password === password && user.role === role;
    }

    function setupMobileMenu() {
        const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
        const navLinks = document.getElementById('nav-links');
        if (mobileMenuBtn) {
            mobileMenuBtn.addEventListener('click', () => {
                navLinks.classList.toggle('active');
                mobileMenuBtn.setAttribute('aria-expanded', navLinks.classList.contains('active'));
            });
        }
    }

    function showError(message, formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.error('Form not found for error display:', formId);
            alert('Error: ' + message);
            return;
        }
        let errorDiv = form.querySelector('.error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            form.insertAdjacentElement('beforeend', errorDiv);
        }
        errorDiv.textContent = message;
        setTimeout(() => { errorDiv.textContent = ''; }, 5000);
    }

    function showSuccessMessage(message) {
        const successDiv = document.createElement('div');
        Object.assign(successDiv.style, {
            position: 'fixed', top: '20px', right: '20px', zIndex: '10001',
            background: 'linear-gradient(135deg, #4facfe, #00f2fe)', color: 'white',
            padding: '1rem 2rem', borderRadius: '15px',
            boxShadow: '0 10px 30px rgba(79, 172, 254, 0.3)',
            animation: 'slideInRight 0.5s ease, fadeOut 0.5s ease 2.5s forwards'
        });
        successDiv.textContent = message;
        document.body.appendChild(successDiv);
        setTimeout(() => { successDiv.remove(); }, 3000);
    }
});

// Adding necessary keyframes via JS for the success message animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);


