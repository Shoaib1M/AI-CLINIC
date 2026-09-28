import { useEffect } from 'react'
import { Link, useLocation } from 'react-router'
import {
  ArrowRight,
  CalendarPlus,
  ClipboardList,
  Database,
  FileText,
  KeyRound,
  ShieldAlert,
  Sparkles,
  Stethoscope,
  UserRound,
} from 'lucide-react'
import { useModelInfo } from '../hooks/queries'
import { percent } from '../lib/format'
import { REPO_URL } from '../lib/constants'

const CAPABILITIES = [
  { icon: CalendarPlus, title: 'Appointment booking', text: 'Register new or returning patients, schedule visits and capture symptoms with autocomplete.' },
  { icon: Sparkles, title: 'AI decision support', text: 'A random-forest model ranks the three most likely conditions and states how much its trees agree.' },
  { icon: ClipboardList, title: 'Doctor queue', text: 'Search, filter and sort patients; complete or cancel visits with a clear status history.' },
  { icon: FileText, title: 'Doctor-authored prescriptions', text: 'Doctors write the prescription. The system renders it as a PDF that keeps AI output clearly separate.' },
  { icon: Database, title: 'Persistent records', text: 'Patients, appointments, predictions and prescriptions are stored in MongoDB (Atlas or self-hosted).' },
  { icon: KeyRound, title: 'Role-based access', text: 'JWT sign-in with separate front desk and doctor permissions, enforced by the API.' },
]

const STEPS = [
  { title: 'Front desk books the visit', text: 'Patient details, date, visit type and presenting symptoms.' },
  { title: 'API validates and stores it', text: 'Flask checks every field and saves the appointment in the database.' },
  { title: 'Model suggests, once', text: 'Symptoms are encoded and the random forest ranks conditions. The result is saved with its model version.' },
  { title: 'Doctor reviews', text: 'The queue shows each suggestion next to the symptoms that produced it.' },
  { title: 'Doctor decides and prescribes', text: 'The doctor writes the diagnosis and medication and downloads the PDF.' },
]

const STACK = [
  ['Frontend', 'React 19, Vite, Tailwind CSS, React Router, TanStack Query'],
  ['API', 'Flask 3 blueprints, JWT (PyJWT), server-side validation'],
  ['Data', 'MongoDB (Atlas) via PyMongo, with indexes and atomic counters'],
  ['ML', 'scikit-learn RandomForestClassifier + MultiLabelBinarizer, joblib'],
  ['Documents', 'ReportLab (Platypus) prescription PDFs'],
  ['Quality', 'pytest API/ML/PDF suites, Vitest + Testing Library'],
]

function ProductPreview() {
  const rows = [
    ['Influenza', 0.62],
    ['COVID-19', 0.21],
    ['Pneumonia', 0.09],
  ]
  return (
    <div className="card mx-auto w-full max-w-md overflow-hidden shadow-lg" aria-hidden>
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
        <div>
          <p className="text-sm font-semibold">Aarav Mehta</p>
          <p className="text-xs text-slate-500">Consultation · 10:30</p>
        </div>
        <span className="chip border-amber-200 bg-amber-50 text-amber-800">Pending</span>
      </div>
      <div className="flex flex-wrap gap-1.5 px-5 pt-4">
        {['fever', 'cough', 'fatigue', 'body ache'].map((s) => (
          <span key={s} className="chip border-slate-200 bg-slate-50 font-normal text-slate-600">{s}</span>
        ))}
      </div>
      <div className="m-5 rounded-lg border border-ai-200">
        <p className="flex items-center gap-1.5 border-b border-ai-100 bg-ai-50/60 px-4 py-2 text-xs font-semibold text-ai-700">
          <Sparkles className="size-3.5" /> AI decision support · not a diagnosis
        </p>
        <ul className="space-y-2 px-4 py-3">
          {rows.map(([name, p]) => (
            <li key={name} className="grid grid-cols-[6rem_1fr_2.5rem] items-center gap-3 text-xs">
              <span className="text-slate-700">{name}</span>
              <span className="h-1.5 rounded-full bg-slate-100"><span className="block h-full rounded-full bg-ai-500" style={{ width: `${p * 100}%` }} /></span>
              <span className="text-right text-slate-500">{Math.round(p * 100)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function Home() {
  const { hash } = useLocation()
  const model = useModelInfo()
  const ev = model.data?.loaded ? model.data.evaluation : null

  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' })
  }, [hash])

  return (
    <>
      {/* Hero */}
      <section className="border-b border-slate-100 bg-gradient-to-b from-brand-50/60 to-white">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <p className="chip border-brand-200 bg-white text-brand-800">Open-source portfolio project</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
              Clinic workflow software with transparent AI decision support
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-600">
              AI-CLINIC connects the front desk and the doctor. Symptoms captured at booking are ranked by a
              machine-learning model, and the doctor always makes and records the decision.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/login" className="btn btn-primary px-5 py-2.5">
                Sign in <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link to="/model" className="btn btn-secondary px-5 py-2.5">Read the model card</Link>
            </div>
            <p className="mt-6 text-sm text-slate-500">Educational demo. Not a medical device and not for real patient care.</p>
          </div>
          <ProductPreview />
        </div>
      </section>

      {/* What it does */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6" aria-labelledby="capabilities-heading">
        <p className="eyebrow">What the platform does</p>
        <h2 id="capabilities-heading" className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight">
          The front desk books the visit. The doctor makes the decision.
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {CAPABILITIES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-xl border border-slate-200 p-5">
              <span className="inline-grid size-9 place-items-center rounded-lg bg-brand-50 text-brand-700"><Icon className="size-5" aria-hidden /></span>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1.5 text-sm text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow */}
      <section id="how-it-works" className="scroll-mt-20 border-y border-slate-100 bg-slate-50" aria-labelledby="workflow-heading">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <p className="eyebrow">How the workflow works</p>
          <h2 id="workflow-heading" className="mt-2 text-3xl font-semibold tracking-tight">From booking to prescription in five steps</h2>
          <ol className="mt-10 grid gap-4 md:grid-cols-5">
            {STEPS.map((step, i) => (
              <li key={step.title} className="card p-5">
                <span className="grid size-7 place-items-center rounded-full bg-brand-700 text-xs font-semibold text-white">{i + 1}</span>
                <h3 className="mt-3 text-sm font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* AI explanation */}
      <section className="mx-auto grid max-w-6xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2" aria-labelledby="ai-heading">
        <div>
          <p className="eyebrow">How the AI suggestion is made</p>
          <h2 id="ai-heading" className="mt-2 text-3xl font-semibold tracking-tight">A simple model, measured honestly</h2>
          <div className="mt-5 space-y-4 text-slate-600">
            <p>
              Each symptom becomes one column in a 0/1 vector (<em>MultiLabelBinarizer</em>). A <em>random forest</em> of
              200 decision trees votes on the condition. The API returns the top three conditions and the share of votes
              each one received.
            </p>
            <p>
              That share is <strong>model confidence</strong>, which measures agreement between trees. It is not a
              clinical probability. Symptoms the model has never seen are flagged and ignored, not guessed.
            </p>
            <p>
              Evaluation groups identical symptom combinations so none appears in both training and test data. This
              gives a lower but more honest number than a plain random split.
            </p>
          </div>
        </div>
        <div className="grid content-start gap-4 sm:grid-cols-2">
          {[
            ['Grouped CV accuracy', ev?.grouped_cv ? `${percent(ev.grouped_cv.accuracy.mean, 1)} ± ${percent(ev.grouped_cv.accuracy.std, 1)}` : '—'],
            ['Top-3 accuracy', ev ? percent(ev.holdout.top3_accuracy, 1) : '—'],
            ['Conditions', model.data?.classes?.length ?? '—'],
            ['Known symptoms', model.data?.symptoms?.length ?? '—'],
          ].map(([label, value]) => (
            <div key={label} className="card p-5">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
            </div>
          ))}
          <p className="text-xs text-slate-500 sm:col-span-2">
            Measured on a synthetic dataset of 1,000 rows. <Link to="/model" className="font-medium text-brand-700 hover:underline">See the full model card →</Link>
          </p>
        </div>
      </section>

      {/* Roles */}
      <section className="border-y border-slate-100 bg-slate-50" aria-labelledby="roles-heading">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <p className="eyebrow">Two roles</p>
          <h2 id="roles-heading" className="mt-2 text-3xl font-semibold tracking-tight">Each role sees only its own tools</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {[
              { icon: UserRound, title: 'Front desk', items: ['Register new and returning patients', 'Book, reschedule, cancel and reinstate visits', 'Enter symptoms with model-vocabulary autocomplete', 'See a live AI preview before booking'] },
              { icon: Stethoscope, title: 'Doctor', items: ['Overview of pending, completed and cancelled visits', 'Search, filter by status or suggested condition, sort', 'Review ranked AI suggestions with warnings', 'Write prescriptions and download PDFs'] },
            ].map(({ icon: Icon, title, items }) => (
              <div key={title} className="card p-6">
                <h3 className="flex items-center gap-2 text-lg font-semibold"><Icon className="size-5 text-brand-700" aria-hidden /> {title}</h3>
                <ul className="mt-4 space-y-2 text-sm text-slate-600">
                  {items.map((item) => <li key={item} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden />{item}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Technology */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6" aria-labelledby="tech-heading">
        <p className="eyebrow">Technology</p>
        <h2 id="tech-heading" className="mt-2 text-3xl font-semibold tracking-tight">A React client talking to a Flask REST API</h2>
        <dl className="mt-8 grid gap-x-8 gap-y-4 sm:grid-cols-2">
          {STACK.map(([k, v]) => (
            <div key={k} className="flex flex-col border-b border-slate-100 pb-4 sm:flex-row sm:gap-4">
              <dt className="w-28 shrink-0 text-sm font-semibold text-slate-900">{k}</dt>
              <dd className="text-sm text-slate-600">{v}</dd>
            </div>
          ))}
        </dl>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
          Architecture and API docs on GitHub <ArrowRight className="size-4" aria-hidden />
        </a>
      </section>

      {/* Safety */}
      <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6" aria-labelledby="safety-heading">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 sm:p-8">
          <h2 id="safety-heading" className="flex items-center gap-2 text-xl font-semibold text-amber-950">
            <ShieldAlert className="size-5" aria-hidden /> Safety and limitations
          </h2>
          <ul className="mt-4 grid gap-3 text-sm text-amber-900 md:grid-cols-2">
            <li>The model was trained on a small <strong>synthetic</strong> dataset and has <strong>not been clinically validated</strong>.</li>
            <li>Predictions are educational decision support, <strong>not diagnoses</strong>. It always picks one of ten conditions.</li>
            <li>Prescriptions are written by a qualified clinician. The AI never prescribes.</li>
            <li>Do not enter real patient data. Authentication and storage are sized for a demo, not for regulated health data.</li>
          </ul>
        </div>
      </section>
    </>
  )
}
