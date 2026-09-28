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
│  models/ (SQLAlchemy)   ml/ (scikit-learn)     services/pdf_service │
│  SQLite file            loaded once at start   ReportLab Platypus  │
└───────────────────────────────────────────────────────────────────┘
        ▲                          ▲
        │                          │ reads artifacts (never trains)
  server/instance/ai_clinic.db     models/*.joblib + model_metadata.json
                                   ▲
                                   │ written by the offline pipeline
                        server/scripts/train_model.py ← data/*.csv
```

## Request lifecycle: booking an appointment

1. `NewAppointment.jsx` validates the form client-side for fast feedback, then calls `useCreateAppointment()` → `api.createAppointment()` → `POST /api/appointments` with the JWT.
2. `routes/appointments.py` is decorated `@require_auth("frontdesk")`. The decorator verifies the token's signature and expiry, loads the user from the DB, and checks the role.
3. `validate_appointment_create()` re-checks every field. It reports all errors at once, as `{"details": {"patient.phone": …}}`, which the form maps back onto its inputs.
4. `appointment_service.create_appointment()` reuses or creates the `Patient`, creates the `Appointment`, and calls `prediction_service.prediction_record_for(symptoms)`. That call uses the in-memory predictor and returns a `Prediction` row. It never raises, so a model problem cannot block a booking.
5. One transaction commits all three rows. A structured log event `appointment_created` records ids only: no names, phones or symptoms.
6. The JSON response updates the UI. TanStack Query invalidates the cached `appointments` queries, so both dashboards refresh.

## Data model

```
users ──────────────┐ created_by                 ┌──── doctor_id ───── users
                    ▼                            │
patients 1 ──── * appointments 1 ──── 0..1 predictions
                        │
                        └──── 1 ──── * prescriptions
```

| Table | Why it exists | Key fields |
| --- | --- | --- |
| `users` | Staff accounts for auth and audit ("booked by", "prescribed by") | `username` (unique), `password_hash`, `role`, `is_active` |
| `patients` | A person seen more than once should be one record; enables visit history and returning-patient search | `full_name`, `phone` (indexed, not unique: families share numbers) |
| `appointments` | The visit: when, what type, which state, which symptoms | `scheduled_at`, `appointment_type`, `status`, `symptoms` (JSON list) |
| `predictions` | Model output is kept **separate from clinician data** and stamped with `model_version`, so every suggestion is traceable to the model that made it | `status`, `predicted_disease`, `confidence`, `top_predictions` (JSON), `unknown_symptoms`, `model_version` |
| `prescriptions` | Doctor-authored, one-to-many per visit (a revised prescription is a new row, not an edit) | `doctor_id`, `diagnosis`, `medications` (JSON list of `{name, dosage, instructions}`), `notes` |

All tables have `created_at` / `updated_at` (UTC).

**Why JSON columns for symptoms and medications?** They are always read and written as a whole with their parent, never queried relationally on their own. Symptom search uses a simple `LIKE` over the serialised list. A `symptoms` table with a many-to-many join would add three tables and joins for no current query. If the product needed symptom analytics, normalising them would be the next step.

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

### Why SQLite?

The goal is "clone, install, run" with persistence that survives restarts. SQLite is a file (`server/instance/ai_clinic.db`) with no server to install, it supports transactions and foreign keys, and it handles a single-clinic demo easily. `DATABASE_URL` accepts any SQLAlchemy URL, so moving to PostgreSQL is a configuration change plus a driver.

### Why SQLAlchemy?

- ORM models are the **schema in code**: typed columns, relationships and `to_dict()` serialisers in one place.
- Queries are parameterised, so there is no SQL injection. Search uses `.contains(..., autoescape=True)`, which treats user-typed `%` and `_` literally.
- `selectinload` avoids N+1 queries when listing appointments with their patient, prediction and prescriptions.
- The same code runs on SQLite and PostgreSQL.

Tables are created with `db.create_all()` at startup to keep setup to zero steps. A production system would manage schema changes with Alembic migrations (listed in future work).

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
| Configuration | `app/config.py` reads env vars (`.env` at repo root via python-dotenv). Development, testing and production classes. Production refuses to start without a ≥ 32-char `JWT_SECRET`. |
| Validation | `utils/validators.py`: explicit functions returning cleaned data or `ValidationError` with per-field details. Unknown fields on `PATCH` are rejected (no mass assignment). |
| Errors | `errors.py`: an `APIError` hierarchy mapped to status codes. HTTP exceptions become JSON. Unexpected exceptions are logged with a stack trace and returned as a generic 500. |
| Logging | `logging_config.py`: text locally, one JSON object per line with `LOG_FORMAT=json`. Events include `app_started`, `model_loaded`, `model_load_failed`, `prediction_made`, `appointment_created`, `appointment_updated`, `prescription_created`, `pdf_generated`, `pdf_generation_failed`, `login_succeeded` and `login_failed`. Patient names, phones and symptoms are never logged. |
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
