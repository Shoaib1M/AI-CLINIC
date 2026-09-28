import { AlertTriangle, Info, Sparkles } from 'lucide-react'
import { percent } from '../lib/format'

const LEVEL_TEXT = {
  high: 'Strong agreement between trees',
  moderate: 'Moderate agreement between trees',
  low: 'Weak agreement: treat with caution',
}

// Accepts both the stored record ({predicted_disease, status}) and the
// /api/predictions preview ({prediction}).
function normalise(p) {
  return {
    status: p.status || 'ok',
    disease: p.predicted_disease ?? p.prediction,
    confidence: p.confidence,
    level: p.confidence_level,
    top: p.top_predictions || [],
    warnings: p.warnings || [],
    treatments: p.reference_treatments || [],
    version: p.model_version,
  }
}

export function AiBadge() {
  return (
    <span className="chip border-ai-200 bg-ai-50 text-ai-700">
      <Sparkles className="size-3" aria-hidden /> AI suggestion · not a diagnosis
    </span>
  )
}

export function PredictionCard({ prediction, showTreatments = false, compact = false, title = 'AI decision support' }) {
  if (!prediction) return null
  const p = normalise(prediction)

  return (
    <section className="card overflow-hidden border-ai-200" aria-label={title}>
      <div className="flex items-center justify-between gap-2 border-b border-ai-100 bg-ai-50/60 px-5 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ai-700">
          <Sparkles className="size-4" aria-hidden /> {title}
        </h2>
        <span className="text-[11px] font-medium tracking-wide text-ai-600 uppercase">Not a diagnosis</span>
      </div>

      <div className="space-y-4 px-5 py-4">
        {p.status === 'no_known_symptoms' && (
          <p className="text-sm text-slate-600">
            None of the recorded symptoms are in the model&apos;s vocabulary, so no suggestion was made.
          </p>
        )}
        {p.status === 'model_unavailable' && (
          <p className="text-sm text-slate-600">The model was unavailable when this appointment was booked.</p>
        )}

        {p.status === 'ok' && (
          <>
            <div>
              <p className="eyebrow">Most likely pattern</p>
              <p className="mt-0.5 text-xl font-semibold tracking-tight text-slate-900">{p.disease}</p>
              <p className="mt-0.5 text-sm text-slate-500">
                Model confidence <span className="font-medium text-slate-700">{percent(p.confidence)}</span>
                {p.level && <> · {LEVEL_TEXT[p.level]}</>}
              </p>
            </div>

            {p.top.length > 1 && (
              <div>
                <p className="eyebrow mb-2">Top {p.top.length} candidates</p>
                <ul className="space-y-2">
                  {p.top.map(({ disease, probability }) => (
                    <li key={disease} className="grid grid-cols-[minmax(0,8.5rem)_1fr_2.75rem] items-center gap-3 text-sm">
                      <span className="truncate text-slate-700" title={disease}>{disease}</span>
                      <span className="h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                        <span className="block h-full rounded-full bg-ai-500" style={{ width: `${Math.max(probability * 100, 1.5)}%` }} />
                      </span>
                      <span className="text-right text-xs font-medium text-slate-600 tabular-nums">{percent(probability)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        {p.warnings.length > 0 && (
          <ul className="space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            {p.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden /> {w}
              </li>
            ))}
          </ul>
        )}

        {showTreatments && p.status === 'ok' && (
          <div>
            <p className="eyebrow">Treatments recorded in the training data</p>
            {p.treatments.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {p.treatments.map((t) => (
                  <span key={t} className="chip border-slate-200 bg-slate-50 text-slate-700">{t}</span>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-sm text-slate-500">None recorded for this condition in the dataset.</p>
            )}
            <p className="hint">Reference information from a synthetic dataset. It is not a prescription.</p>
          </div>
        )}

        {!compact && (
          <p className="flex gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
            <Info className="mt-px size-3.5 shrink-0" aria-hidden />
            <span>
              “Confidence” is the share of the random forest&apos;s trees that agree. It is not the probability that the
              patient has this condition. Educational model trained on synthetic data.
              {p.version && <span className="block text-slate-400">Model {p.version}</span>}
            </span>
          </p>
        )}
      </div>
    </section>
  )
}
