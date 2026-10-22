# AI-CLINIC REST API

Base URL: `http://127.0.0.1:5000/api` locally. In development the React client calls `/api` on its own origin and Vite proxies it to Flask.

All examples below are real responses captured from the running API. Some are shortened where marked `…`.

## Conventions

**Content type.** Requests and responses are JSON (`Content-Type: application/json`), except the PDF download.

**Success envelope.** Every successful response wraps its payload in `data`. List endpoints add `meta` with pagination:

```json
{ "data": [ … ], "meta": { "page": 1, "per_page": 20, "total": 13, "pages": 1 } }
```

**Error envelope.** Every error has the same shape. `details` is present for field-level problems.

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "The request contains invalid data.",
    "details": { "patient.phone": "Enter a valid phone number (7–15 digits).", "symptoms": "At least one symptom is required." }
  }
}
```

| Status | When | Example `code` |
| --- | --- | --- |
| 400 | Malformed JSON, missing or invalid fields, bad query parameters | `INVALID_JSON`, `INVALID_INPUT` |
| 401 | Missing, invalid or expired token; wrong credentials | `UNAUTHENTICATED`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `INVALID_CREDENTIALS` |
| 403 | Authenticated, but the role may not do this | `FORBIDDEN` |
| 404 | Unknown resource or route | `APPOINTMENT_NOT_FOUND`, `PATIENT_NOT_FOUND`, `PRESCRIPTION_NOT_FOUND`, `NOT_FOUND` |
| 405 | Wrong HTTP method | `METHOD_NOT_ALLOWED` |
| 409 | Valid request that conflicts with current state | `INVALID_STATUS_TRANSITION`, `APPOINTMENT_NOT_PENDING`, `APPOINTMENT_CANCELLED`, `CONCURRENT_UPDATE` |
| 413 | Body larger than 64 KB | `PAYLOAD_TOO_LARGE` |
| 422 | Well-formed, but the model cannot use any of the symptoms | `NO_KNOWN_SYMPTOMS` |
| 500 | Unexpected server error (details are logged, never returned) | `INTERNAL_ERROR`, `PDF_GENERATION_FAILED` |
| 503 | Model artifacts not loaded, or MongoDB unreachable | `MODEL_UNAVAILABLE`, `DATABASE_UNAVAILABLE` |

**Authentication.** Send `Authorization: Bearer <token>` with the token from `POST /api/auth/login`. Tokens are HS256 JWTs and expire after `JWT_EXPIRES_MINUTES` (default 8 hours). The server reads the user's role from the database on every request, not from the token, so deactivating a user takes effect immediately.

**Dates.** `scheduled_at` is clinic-local time without an offset (`YYYY-MM-DDTHH:MM`). Audit timestamps (`created_at`, `updated_at`) are UTC and end in `Z`.

**Enumerations.**

- `appointment_type`: `regular_checkup`, `follow_up`, `consultation`, `emergency`
- `status`: `pending`, `completed`, `cancelled`
- `role`: `doctor`, `frontdesk`

## Endpoint summary

| Method | Endpoint | Auth | Purpose | Request | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/health` | public | Liveness and readiness | — | status, database, model |
| POST | `/api/auth/login` | public | Exchange credentials for a JWT | `username`, `password` | token, expiry, user |
| GET | `/api/auth/me` | any role | Current user | — | user |
| GET | `/api/appointments` | doctor, frontdesk | Search, filter, sort, paginate | query params | appointment list + `meta` |
| POST | `/api/appointments` | frontdesk | Book a visit; runs and stores the AI suggestion | patient, time, type, symptoms | appointment (201) |
| GET | `/api/appointments/stats` | doctor, frontdesk | Dashboard counts | — | stats |
| GET | `/api/appointments/:id` | doctor, frontdesk | Full record with prescriptions and visit history | — | appointment |
| PATCH | `/api/appointments/:id` | doctor, frontdesk | Change status, reschedule | `status`, `scheduled_at`, `appointment_type` | appointment |
| GET | `/api/patients?q=` | doctor, frontdesk | Patient typeahead | `q` (≥ 2 chars) | patients |
| POST | `/api/predictions` | doctor, frontdesk | Stateless prediction (preview) | `symptoms`, `top_k` | prediction |
| GET | `/api/model` | public | Model card: vocabulary, classes, metrics | — | model info |
| POST | `/api/prescriptions` | doctor | Doctor-authored prescription | appointment, diagnosis, medications | prescription (201) |
| GET | `/api/prescriptions/:id` | doctor, frontdesk | Read a prescription | — | prescription |
| GET | `/api/prescriptions/:id/pdf` | doctor, frontdesk | Download the PDF | — | `application/pdf` |

There is deliberately no `DELETE /api/appointments/:id`. Clinical records are not hard-deleted; the audited path is cancellation (`PATCH` with `"status": "cancelled"`).

---

## Health

### `GET /api/health`

Public. Returns 200 when the database is reachable. `status` is `degraded` when the model is not loaded, and the response is 503 when the database is down.

```bash
curl http://127.0.0.1:5000/api/health
```

```json
{ "data": { "status": "ok", "database": "ok", "model": { "loaded": true, "version": "rf-baseline-20260927-8e254518" } } }
```

## Authentication

### `POST /api/auth/login`

| Field | Type | Rules |
| --- | --- | --- |
| `username` | string | required |
| `password` | string | required |

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "frontdesk1", "password": "<your password>"}'
```

```json
{
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_at": "2026-09-28T11:06:18+00:00",
    "user": { "id": 2, "username": "frontdesk1", "full_name": "Sarah Johnson", "role": "frontdesk" }
  }
}
```

Errors: `400 INVALID_INPUT` (missing fields), `401 INVALID_CREDENTIALS`. The response for a wrong password is identical to the one for an unknown user, and both take the same time, so the endpoint does not reveal which usernames exist.

### `GET /api/auth/me`

Returns the signed-in user (`data` has the same shape as `user` above). Errors: `401`.

## Appointments

### `POST /api/appointments` (frontdesk)

Creates the appointment, runs the model **once**, and stores the result as the appointment's `prediction`, stamped with the model version. Booking never fails because of the model. If no symptom is recognised, or the model is not loaded, the appointment is still created, and `prediction.status` is `no_known_symptoms` or `model_unavailable`.

Send **either** `patient_id` (returning patient) **or** `patient` (new patient). A new patient whose name (case-insensitive) and phone match an existing record reuses that record.

| Field | Type | Rules |
| --- | --- | --- |
| `patient_id` | integer | existing patient id |
| `patient.full_name` | string | 2–100 chars; letters of any script, spaces, `.'-` |
| `patient.phone` | string | `+`, digits, spaces, `()-`; 7–15 digits |
| `scheduled_at` | string | `YYYY-MM-DDTHH:MM`, today or later, at most one year ahead, no timezone offset |
| `appointment_type` | string | one of the enumeration |
| `symptoms` | string[] | 1–15 items, each ≤ 60 chars. A comma-separated string is also accepted for compatibility. Items are lower-cased, trimmed and de-duplicated. |

```bash
curl -X POST http://127.0.0.1:5000/api/appointments \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
        "patient": {"full_name": "Riya Kapoor", "phone": "+91 99887 76655"},
        "scheduled_at": "2026-10-02T10:30",
        "appointment_type": "consultation",
        "symptoms": ["fever", "chills", "vomiting", "nausea"]
      }'
```

```json
{
  "data": {
    "id": 13,
    "patient": { "id": 13, "full_name": "Riya Kapoor", "phone": "+91 99887 76655", "created_at": "2026-09-28T03:06:18Z" },
    "scheduled_at": "2026-10-02T10:30",
    "appointment_type": "consultation",
    "status": "pending",
    "symptoms": ["fever", "chills", "vomiting", "nausea"],
    "prediction": {
      "status": "ok",
      "predicted_disease": "Malaria",
      "confidence": 0.915,
      "confidence_level": "high",
      "top_predictions": [
        { "disease": "Malaria", "probability": 0.915 },
        { "disease": "Gastroenteritis", "probability": 0.06 },
        { "disease": "Influenza", "probability": 0.01 }
      ],
      "recognized_symptoms": ["fever", "chills", "vomiting", "nausea"],
      "unknown_symptoms": [],
      "reference_treatments": ["Chloroquine", "Artemether", "Primaquine"],
      "warnings": [],
      "model_version": "rf-baseline-20260927-8e254518",
      "created_at": "2026-09-28T03:06:18Z"
    },
    "prescription_count": 0,
    "prescriptions": [],
    "created_by": { "id": 2, "username": "frontdesk1", "full_name": "Sarah Johnson", "role": "frontdesk" },
    "created_at": "2026-09-28T03:06:18Z",
    "updated_at": "2026-09-28T03:06:18Z"
  }
}
```

Errors: `400 INVALID_INPUT` (all bad fields reported together), `401`, `403` (doctor), `404 PATIENT_NOT_FOUND`.

### `GET /api/appointments` (doctor, frontdesk)

| Query | Default | Meaning |
| --- | --- | --- |
| `q` | — | Case-insensitive match on patient name, phone, predicted disease or symptom. Regex characters such as `.*` are matched literally. |
| `status` | — | `pending`, `completed` or `cancelled` |
| `disease` | — | Exact AI-suggested condition |
| `date_from`, `date_to` | — | `YYYY-MM-DD`, inclusive, on `scheduled_at` |
| `sort` | `scheduled_at` | `scheduled_at`, `created_at`, `patient_name`, `confidence` |
| `order` | `desc` | `asc` or `desc` (nulls always last) |
| `page` | 1 | ≥ 1 |
| `per_page` | 20 | 1–100 |

```bash
curl "http://127.0.0.1:5000/api/appointments?status=pending&sort=confidence&order=desc&per_page=10" -H "Authorization: Bearer $TOKEN"
```

Response: `data` is a list of appointments (same shape as above, without `created_by` and `prescriptions`), plus `meta`. Errors: `400` for invalid parameters.

### `GET /api/appointments/stats` (doctor, frontdesk)

```json
{
  "data": {
    "total_appointments": 13,
    "by_status": { "pending": 10, "completed": 2, "cancelled": 1 },
    "scheduled_today": 4,
    "total_patients": 13,
    "top_predicted_diseases": [ { "disease": "COVID-19", "count": 2 }, { "disease": "Influenza", "count": 2 }, … ]
  }
}
```

### `GET /api/appointments/:id` (doctor, frontdesk)

Full record: everything from the create response, plus `prescriptions` (newest first) and `visit_history` (up to 10 other visits by the same patient: `id`, `scheduled_at`, `appointment_type`, `status`, `predicted_disease`). Errors: `404 APPOINTMENT_NOT_FOUND`.

### `PATCH /api/appointments/:id` (doctor, frontdesk)

Only these fields are accepted; anything else is a `400`:

| Field | Rules |
| --- | --- |
| `status` | Allowed transitions: `pending → completed`, `pending → cancelled`, `cancelled → pending`. `completed` is final. Only a doctor can set `completed`; front desk can cancel or reinstate. |
| `scheduled_at` | Same rules as on create. Only while `pending`. |
| `appointment_type` | Only while `pending`. |

```bash
curl -X PATCH http://127.0.0.1:5000/api/appointments/13 \
  -H "Authorization: Bearer $DOCTOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"status": "completed"}'
```

Response: the updated appointment. Errors: `400`, `403` (e.g. front desk completing a visit), `404`, `409`:

```json
{ "error": { "code": "INVALID_STATUS_TRANSITION", "message": "Cannot change status from 'completed' to 'pending'." } }
```

If two people change the same appointment at the same moment, the second request gets `409 CONCURRENT_UPDATE` instead of overwriting the first; reload and retry.

## Patients

### `GET /api/patients?q=riya` (doctor, frontdesk)

Typeahead for returning patients. Returns at most 10 matches on name or phone, most recently seen first. A query shorter than 2 characters returns `[]`.

```json
{
  "data": [
    { "id": 13, "full_name": "Riya Kapoor", "phone": "+91 99887 76655", "visit_count": 1, "last_visit": "2026-10-02T10:30", "created_at": "2026-09-28T03:06:18Z" },
    { "id": 2, "full_name": "Priya Nair", "phone": "+91 98100 11202", "visit_count": 1, "last_visit": "2026-09-27T11:00", "created_at": "2026-09-28T03:06:15Z" }
  ]
}
```

## Predictions

### `POST /api/predictions` (doctor, frontdesk)

Stateless: nothing is stored. The front desk uses it for the live preview while typing symptoms. Authentication is required so the endpoint cannot be used anonymously.

| Field | Type | Rules |
| --- | --- | --- |
| `symptoms` | string[] | as on appointment creation |
| `top_k` | integer | 1–10, default 3 |

```bash
curl -X POST http://127.0.0.1:5000/api/predictions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"symptoms": ["fever", "chills", "vomiting", "nausea", "telepathy"]}'
```

```json
{
  "data": {
    "prediction": "Malaria",
    "confidence": 0.915,
    "confidence_level": "high",
    "top_predictions": [
      { "disease": "Malaria", "probability": 0.915 },
      { "disease": "Gastroenteritis", "probability": 0.06 },
      { "disease": "Influenza", "probability": 0.01 }
    ],
    "recognized_symptoms": ["fever", "chills", "vomiting", "nausea"],
    "unknown_symptoms": ["telepathy"],
    "reference_treatments": ["Chloroquine", "Artemether", "Primaquine"],
    "warnings": ["1 symptom(s) not recognised by the model and ignored: telepathy."],
    "model_version": "rf-baseline-20260927-8e254518",
    "disclaimer": "Educational decision-support output from a model trained on a small synthetic dataset. It is not a diagnosis and has not been clinically validated. 'confidence' is the share of decision-tree votes, not the probability of disease."
  }
}
```

Field meanings:

- `confidence` is the fraction of the forest's trees voting for `prediction` (averaged leaf class shares). It is **model confidence**, not clinical certainty. See [ML.md](ML.md#confidence-what-it-is-and-is-not).
- `confidence_level` is `high` (≥ 0.7), `moderate` (≥ 0.4) or `low`.
- `warnings` flags ignored symptoms and inputs with fewer than 3 recognised symptoms (training rows have 4–5).
- `reference_treatments` lists the most frequent treatments recorded for that condition in the synthetic dataset. It is reference information, not a prescription, and is empty for 5 of the 10 conditions.

Errors: `400` (malformed input), `422 NO_KNOWN_SYMPTOMS` (with `details.unknown_symptoms`), `503 MODEL_UNAVAILABLE`.

### `GET /api/model` (public)

Model card data: `model_version`, `algorithm`, `hyperparameters`, `trained_at`, `sklearn_version`, `classes`, `symptoms` (vocabulary), `symptom_aliases`, `dataset` (rows, hash, duplicates, class distribution), `evaluation` (grouped hold-out metrics incl. per-class and confusion matrix, grouped CV, random-split accuracy) and `disclaimer`. Returns `{"loaded": false, …}` when no model is loaded.

## Prescriptions

### `POST /api/prescriptions` (doctor)

The prescriber is always the signed-in doctor. A doctor name in the request body is ignored, which fixes the old endpoint that would print any name it was given.

| Field | Type | Rules |
| --- | --- | --- |
| `appointment_id` | integer | must exist and not be cancelled |
| `diagnosis` | string | 2–200 chars, written by the doctor |
| `medications` | object[] | 1–20 items: `name` (required, ≤ 100), `dosage` (≤ 100), `instructions` (≤ 300) |
| `notes` | string | optional, ≤ 2000 |

```bash
curl -X POST http://127.0.0.1:5000/api/prescriptions \
  -H "Authorization: Bearer $DOCTOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"appointment_id": 13, "diagnosis": "Malaria (suspected)",
       "medications": [{"name": "Chloroquine", "dosage": "As per weight", "instructions": "Start after blood smear confirmation"}],
       "notes": "Review in 3 days."}'
```

```json
{
  "data": {
    "id": 3,
    "appointment_id": 13,
    "doctor": { "id": 1, "username": "doctor1", "full_name": "Dr. Evelyn Reed", "role": "doctor" },
    "diagnosis": "Malaria (suspected)",
    "medications": [ { "name": "Chloroquine", "dosage": "As per weight", "instructions": "Start after blood smear confirmation" } ],
    "notes": "Review in 3 days.",
    "created_at": "2026-09-28T03:06:18Z"
  }
}
```

Errors: `400`, `403` (front desk), `404 APPOINTMENT_NOT_FOUND`, `409 APPOINTMENT_CANCELLED`.

### `GET /api/prescriptions/:id` (doctor, frontdesk)

Returns the prescription object above. Errors: `404 PRESCRIPTION_NOT_FOUND`.

### `GET /api/prescriptions/:id/pdf` (doctor, frontdesk)

Returns `application/pdf` as an attachment named `prescription_RX-000003.pdf`. The filename contains no patient data. The PDF shows the clinic, patient, appointment, prescriber, diagnosis, medication table, notes and signature line. A separate, labelled box records the AI suggestion made at intake, and a footer disclaimer appears on every page.

```bash
curl -OJ http://127.0.0.1:5000/api/prescriptions/3/pdf -H "Authorization: Bearer $TOKEN"
```

Errors: `404`, `500 PDF_GENERATION_FAILED`.

## Removed legacy endpoints

| Old | Replacement | Why |
| --- | --- | --- |
| `GET /`, `/frontdesk`, `/doctor` (HTML) | React client | Flask no longer renders pages |
| `PUT /api/appointments/<id>` | `PATCH /api/appointments/:id` | Partial update, validated transitions and roles |
| `POST /api/generate-pdf`, `/generate-pdf`, `/api/generate-pdf-base64` | `POST /api/prescriptions` + `GET /api/prescriptions/:id/pdf` | The old routes were unauthenticated and accepted arbitrary patient and doctor names |
| `GET /api/generate-pdf/<id>` | same as above | It printed "Dr. System" and the AI's treatment list as if they were a prescription |
| `GET /test-pdf` | removed | Debug route |
