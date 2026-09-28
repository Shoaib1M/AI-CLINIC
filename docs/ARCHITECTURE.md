# Architecture

AI-CLINIC is a single-page React application that talks to a Flask REST API over JSON. The API owns everything with rules: persistence, authentication, validation, the ML model and PDF generation.

```
┌──────────────────────────── Browser ────────────────────────────┐
│  React 19 SPA (Vite build)                                       │
│  pages → components → hooks (TanStack Query) → lib/api.js        │
└───────────────────────────────┬──────────────────────────────────┘
                                │  HTTPS · JSON · Authorization: Bearer <JWT>
┌───────────────────────────────▼──────────────────────────────────┐
│  Flask API  (server/app)                                          │
│                                                                   │
│  routes/        blueprints: parse request, check auth, call a service │
│     │           (@require_auth checks the JWT and the role)       │
│  utils/validators.py   untrusted JSON → cleaned dict or 400       │
│     │                                                             │
│  services/      business rules (status transitions, role rules,   │
│     │           patient reuse, "booking never depends on the model")│
│     ├──────────────────────┬─────────────────────┬────────────────┤
│  models/ (documents)    ml/ (scikit-learn)     services/pdf_service │
│  PyMongo → MongoDB      loaded once at start   ReportLab Platypus  │
└───────────────────────────────────────────────────────────────────┘
        ▲                          ▲
        │                          │ reads artifacts (never trains)
  MongoDB Atlas cluster            models/*.joblib + model_metadata.json
                                   ▲
                                   │ written by the offline pipeline
                        server/scripts/train_model.py ← data/*.csv
```

## Request lifecycle: booking an appointment

1. `NewAppointment.jsx` validates the form client-side for fast feedback, then calls `useCreateAppointment()` → `api.createAppointment()` → `POST /api/appointments` with the JWT.
2. `routes/appointments.py` is decorated `@require_auth("frontdesk")`. The decorator verifies the token's signature and expiry, loads the user from the DB, and checks the role.
3. `validate_appointment_create()` re-checks every field. It reports all errors at once, as `{"details": {"patient.phone": …}}`, which the form maps back onto its inputs.
4. `appointment_service.create_appointment()` reuses or creates the patient document, then calls `prediction_service.prediction_record_for(symptoms)`. That call uses the in-memory predictor and returns the prediction sub-document. It never raises, so a model problem cannot block a booking.
5. A single `insert_one` writes the appointment **with its prediction embedded**, so that write is atomic. A structured log event `appointment_created` records ids only: no names, phones or symptoms.
6. The JSON response updates the UI. TanStack Query invalidates the cached `appointments` queries, so both dashboards refresh.

## Data model (MongoDB)

```
users ─────────────┐ created_by_id                ┌──── doctor_id ───── users
                   ▼                              │
patients 1 ──── * appointments ──── 1 ──── * prescriptions
                   └─ prediction  (embedded sub-document)
counters           one document per collection: {_id: "appointments", seq: 13}
```

| Collection | Why it exists | Key fields | Indexes |
| --- | --- | --- | --- |
| `users` | Staff accounts for auth and audit ("booked by", "prescribed by") | `username`, `password_hash`, `role`, `is_active` | `username` unique |
| `patients` | A person seen more than once is one record; enables visit history and returning-patient search | `full_name`, `full_name_lower`, `phone` | (`full_name_lower`, `phone`) unique; `phone` |
| `appointments` | The visit: when, what type, which state, which symptoms, **plus the AI suggestion embedded as `prediction`** | `patient_id`, `scheduled_at`, `appointment_type`, `status`, `symptoms` (array), `prediction` (sub-document), `prescription_count` | `patient_id`, `status`, `scheduled_at`, `prediction.predicted_disease` |
| `prescriptions` | Doctor-authored, one-to-many per visit (a revised prescription is a new document, not an edit) | `appointment_id`, `doctor_id`, `diagnosis`, `medications` (array of `{name, dosage, instructions}`), `notes` | `appointment_id` |
| `counters` | Allocates short sequential ids | `seq` | — |

Every document has `created_at` / `updated_at` (UTC).

**Embed or reference?** The rule used: embed data that is written once with its parent and always read with it; reference data that has its own identity or grows.

- The **prediction is embedded** in the appointment. It is created in the same moment, never edited, and shown wherever the appointment is shown. Embedding makes booking one atomic write and needs no join. It keeps its own `model_version` and `status`, so the AI output stays clearly separate from clinician data.
- **Prescriptions are referenced** (their own collection). They have their own URL (`/api/prescriptions/:id/pdf`), their own author, and a visit can accumulate several.
- **Patients are referenced.** They are shared by many appointments. The appointment also keeps a small **denormalised copy** (`patient_name`, `patient_name_lower`, `patient_phone`), so the doctor's queue can be searched and sorted by patient in one single-collection query. That is safe because patient details are never edited through the API.
- `prescription_count` is kept on the appointment and incremented with `$inc` when a prescription is added, so the list view needs no extra lookup.

**Why integer ids instead of ObjectIds?** Sequential ids keep the REST API exactly as it was (`/api/appointments/13`) and make document numbers readable (A-00013, RX-000003). A `counters` document per collection is incremented with `find_one_and_update($inc)`, which is atomic, so concurrent requests never get the same id.

**Concurrency guards.** A status change is written with `find_one_and_update({_id, status: <status we validated>})`. If two people change the same appointment at once, the second update matches nothing and gets `409 CONCURRENT_UPDATE` instead of silently applying a transition that was only valid from the old state. The unique `(full_name_lower, phone)` index does the same for patient registration: a racing duplicate insert fails, and the service reuses the existing record.

**Why no hard delete?** Clinical records should be auditable. Cancellation (`PATCH status=cancelled`, reversible) is the supported path.

## Decisions

### Why React (and Vite, Tailwind, TanStack Query)?

The original frontend built HTML strings with template literals and `innerHTML`. The same patient card was copy-pasted three times in `script.js`, with inline styles, globals on `window`, and patient names inserted as raw HTML (an XSS hole). React fixes the structural problems directly:

- **Components** remove duplication. `AppointmentList` renders the table on desktop and cards on mobile from one data source.
- **JSX escapes by default**, which closes the XSS class of bugs.
- **Declarative state**: the UI is a function of state, so loading, empty and error states are handled in one place per view.

Vite gives instant dev reloads and a proxy (`/api` → Flask), so there is no CORS in development. Tailwind plus a handful of `@layer components` classes (`.btn`, `.input`, `.card`) form a small design system with tokens in one file (`index.css`). TanStack Query holds **server state** (caching, deduplication, refetch after mutations, `keepPreviousData` for pagination), so components never copy API data into local state. React Router handles navigation; the doctor dashboard keeps its filters in the URL, which makes them shareable and back-button friendly.

### Why a separate Flask REST API instead of Flask-rendered pages?

- **Clear contract.** Every capability is an endpoint documented in [API.md](API.md), testable with pytest's test client without a browser.
- **Independent deployment.** The client is static files on a CDN; the API is a Python process.
- **One place for rules.** Validation, permissions and state transitions live on the server. The client can only make requests, so it cannot skip them.

Flask stays because the project already used it, the ML stack is Python, and its app-factory plus blueprints pattern is small enough to explain in a sentence.

### Why MongoDB (Atlas)?

The records are naturally **document-shaped**: an appointment with an array of symptoms and a nested AI result, and a prescription with a list of medication objects. In a relational schema these became JSON columns or extra join tables; in MongoDB they are plain arrays and sub-documents, stored exactly as the API returns them.

- **Managed hosting.** A free MongoDB Atlas cluster gives a persistent, backed-up database with nothing to install, so the API itself is stateless and can run as several instances.
- **Flexible model output.** Prediction fields such as top-k lists and warnings can grow without migrations, and each suggestion records the model version that produced it.
- **Query needs are simple.** Filter by status or condition, date ranges, case-insensitive text search and group-by counts for the dashboard. Indexes and a small aggregation pipeline cover all of them.

The trade-off: MongoDB does not enforce relationships or a schema. Here the API's validators are the schema, and the few cross-document invariants (unique patients, atomic ids, safe status transitions) are enforced with unique indexes and conditional updates, described above.

### Why PyMongo, not an ODM?

PyMongo is the official driver and keeps every query visible: the filter dicts and aggregation pipelines in `services/` are exactly what runs on the server. An ODM (MongoEngine, Beanie) would add a second modelling layer to learn for five small collections. `models/` holds the document shapes and their JSON serialisers instead.

- **Injection-safe search.** User text is passed through `re.escape()` before it is used in a `$regex`, so `.*` or `(` in the search box match literally and cannot become expensive patterns. Values are always sent as data, never assembled into query strings.
- **Nulls last.** Sorting uses a small `$addFields`/`$sort` pipeline, so appointments without a prediction always sort last, whatever the direction.
- **Stable API.** The client connects with MongoDB Stable API v1 (the same as `mongosh --apiVersion 1`), so server upgrades on Atlas cannot change command behaviour under the app.
- **Tests.** The suite runs on `mongomock`, an in-memory emulator, by default, and against a real server with `TEST_MONGODB_URI`. It passes both ways.

### Why keep the RandomForest?

It was the working core of the original project, it suits the data (binary features, small dataset, non-linear symptom interactions), it trains in seconds, and it gives a vote share that is easy to explain. A controlled comparison showed tuning did not clearly beat it (see [ML.md §7](ML.md#was-the-model-improved-an-honest-answer)). The ML problems were engineering problems (a data-loading bug, leaky evaluation, training inside the web process), not a need for a fancier model.

### Why isolate ML inference?

The original `app.py` mixed data loading, training, evaluation and prediction in the web module and retrained on startup when artifacts were missing. Now:

- **Training** is an offline script that writes versioned artifacts and a metadata file with metrics and a dataset hash.
- **Inference** (`DiseasePredictor`) loads those artifacts once per process, validates them, and exposes `predict()`. It has no Flask or DB imports, so it is unit-tested directly.
- **The service layer** (`prediction_service`) owns the policy: what to do when the model is missing (degrade, don't crash), what to log, and the disclaimer text.

Startup is fast and deterministic, and a bad model file fails loudly with a clear message.

### Why JWT?

The API is stateless and consumed by a separate frontend. A signed token (HS256, secret from `JWT_SECRET`) carries the user id and expiry, so the server needs no session store. The server still loads the user on every request to check `is_active` and read the **current** role from the database, so deactivation and role changes apply immediately. Hardening decisions:

- Algorithm is pinned on decode (rejects `alg: none`).
- `exp`, `iat` and `sub` are required.
- Login returns the same response and timing for "wrong password" and "unknown user".
- Passwords are stored as salted hashes (`werkzeug.security`). Accounts are created from the CLI; no credentials exist in source code or in the client bundle.

**Trade-off.** The client keeps the token in `localStorage` so a refresh keeps you signed in. Any script injected into the page could read it. The mitigations are that React escapes all rendered data, there is no third-party script, and tokens expire. The stronger alternative, an `HttpOnly` `SameSite` cookie plus CSRF protection, is noted as future work.

### Why ReportLab (Platypus)?

ReportLab was already in the project and generates PDFs in pure Python with no headless browser. The rewrite switches from absolute canvas coordinates to **Platypus** flowables (paragraphs and tables), so long medication lists wrap and paginate. Platypus parses a small markup language, so every user-supplied string is XML-escaped first. A test confirms that `<font size=90>` in a diagnosis prints literally.

The PDF is generated from a **stored, doctor-authored prescription** (`GET /api/prescriptions/:id/pdf`), never from free-form request data. The AI suggestion appears only in a separate, labelled "Decision-support note: not part of this prescription" box.

## Cross-cutting concerns

| Concern | Implementation |
| --- | --- |
| Configuration | `app/config.py` reads env vars (`.env` at repo root via python-dotenv). Development, testing and production classes. The app refuses to start without `MONGODB_URI`, and production also requires a ≥ 32-char `JWT_SECRET`. If the cluster is unreachable at startup, the API still starts and reports `database: unavailable` on `/api/health`. |
| Validation | `utils/validators.py`: explicit functions returning cleaned data or `ValidationError` with per-field details. Unknown fields on `PATCH` are rejected (no mass assignment). |
| Errors | `errors.py`: an `APIError` hierarchy mapped to status codes. HTTP exceptions become JSON. MongoDB connection failures become `503 DATABASE_UNAVAILABLE`. Unexpected exceptions are logged with a stack trace and returned as a generic 500. |
| Logging | `logging_config.py`: text locally, one JSON object per line with `LOG_FORMAT=json`. Events include `app_started`, `database_connected`, `database_unreachable`, `model_loaded`, `model_load_failed`, `prediction_made`, `appointment_created`, `appointment_updated`, `prescription_created`, `pdf_generated`, `pdf_generation_failed`, `login_succeeded` and `login_failed`. Patient names, phones and symptoms are never logged. |
| Security headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` on all API responses (patient data). |
| CORS | Only for `/api/*` and only for origins in `CORS_ORIGINS`. |
| Request size | `MAX_CONTENT_LENGTH` of 64 KB. |
| Permissions | Server-side, per endpoint and per action (e.g. front desk may cancel but not complete). Frontend route guards are UX only. |

## Frontend structure

```
client/src/
├── main.jsx                 providers: QueryClient, Router, Toasts, Auth
├── App.jsx                  route table (public / protected / role-guarded)
├── index.css                Tailwind + design tokens (brand = teal, AI = indigo)
├── lib/                     api.js (fetch wrapper), format.js, constants.js, symptoms.js
├── context/                 AuthContext (session), ToastContext
├── hooks/                   queries.js (all server state), useStatusChange, useDebouncedValue
├── components/
│   ├── layout/              AppShell (sidebar/drawer), PublicLayout, ProtectedRoute, Logo
│   ├── ui/                  Modal (native <dialog>), States, StatusBadge, Field
│   └── AppointmentList, SymptomInput, PatientSearch, PredictionCard,
│       PrescriptionDialog, StatCard, Pagination
├── pages/                   Home, Login, FrontDesk, NewAppointment, DoctorDashboard,
│                            AppointmentDetails, ModelInfo, NotFound
└── test/                    Vitest + Testing Library
```

A visual rule makes provenance obvious: anything produced by the model uses the indigo "AI" treatment and says "not a diagnosis". Anything a clinician authored uses the neutral and teal treatment.
