import { AlertTriangle, Database, FlaskConical, Layers } from 'lucide-react'
import { useModelInfo } from '../hooks/queries'
import { formatTimestamp, percent } from '../lib/format'
import { ErrorState, LoadingState } from '../components/ui/States'

// Sequential single-hue ramp (brand teal, light -> dark) for the confusion matrix.
const RAMP = ['#f8fafc', '#ccfbf1', '#99f6e4', '#5eead4', '#14b8a6', '#0f766e', '#134e4a']
const rampIndex = (share) => (share <= 0 ? 0 : Math.min(RAMP.length - 1, 1 + Math.floor(share * (RAMP.length - 1) - 1e-9)))

function Metric({ label, value, detail }) {
  return (
    <div className="card p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
    </div>
  )
}

function ConfusionMatrix({ labels, matrix }) {
  const short = (label) => (label.length > 10 ? `${label.slice(0, 9)}…` : label)
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="table-fixed border-separate border-spacing-0.5 text-xs">
          <caption className="sr-only">Confusion matrix: rows are the true condition, columns the predicted condition</caption>
          <thead>
            <tr>
              <th scope="col" className="p-1 text-left font-medium text-slate-400">True ↓ / Predicted →</th>
              {labels.map((l) => (
                <th key={l} scope="col" className="relative h-24 w-10 min-w-10 p-0 font-medium text-slate-500">
                  <span className="absolute bottom-2 left-1/2 origin-bottom-left -rotate-60 whitespace-nowrap" title={l}>{short(l)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => {
              const total = row.reduce((a, b) => a + b, 0) || 1
              return (
                <tr key={labels[i]}>
                  <th scope="row" className="pr-2 text-right font-medium whitespace-nowrap text-slate-600">{labels[i]}</th>
                  {row.map((count, j) => {
                    const share = count / total
                    const idx = rampIndex(share)
                    const description = `True ${labels[i]}, predicted ${labels[j]}: ${count} of ${total} (${percent(share)})`
                    return (
                      <td
                        key={labels[j]}
                        title={description}
                        aria-label={description}
                        className={`size-10 rounded-[4px] text-center tabular-nums ${idx >= 4 ? 'text-white' : count ? 'text-slate-800' : 'text-slate-300'} ${i === j ? 'font-semibold' : ''}`}
                        style={{ backgroundColor: RAMP[idx] }}
                      >
                        {count}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500" aria-hidden>
        <span>0%</span>
        <span className="flex overflow-hidden rounded">
          {RAMP.map((c) => <span key={c} className="h-2.5 w-6" style={{ backgroundColor: c }} />)}
        </span>
        <span>100% of the true class</span>
      </div>
    </div>
  )
}

export default function ModelInfo() {
  const { data: model, isLoading, isError, error, refetch } = useModelInfo()

  if (isLoading) return <LoadingState label="Loading model card…" />
  if (isError) return <div className="mx-auto max-w-5xl px-4 py-10"><div className="card"><ErrorState error={error} onRetry={refetch} /></div></div>
  if (!model.loaded) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <h1 className="text-2xl font-semibold">Model not loaded</h1>
        <p className="mt-2 text-slate-500">Train it with <code>python -m scripts.train_model</code> in the server directory, then restart the API.</p>
      </div>
    )
  }

  const { evaluation: ev, dataset } = model
  const holdout = ev.holdout
  const cv = ev.grouped_cv

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6">
      <header>
        <p className="eyebrow">Model card</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Symptom-pattern classifier</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          A {model.algorithm} ({model.hyperparameters.n_estimators} trees) over a binary symptom vector built with a
          MultiLabelBinarizer. It ranks {model.classes.length} conditions from {model.symptoms.length} known symptoms.
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Version <code>{model.model_version}</code> · trained {formatTimestamp(model.trained_at)} · scikit-learn {model.sklearn_version}
        </p>
      </header>

      <div role="note" className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden />
        <div>
          <p className="font-semibold">Not clinically validated</p>
          <p className="mt-1">
            Trained and evaluated on {dataset.rows.toLocaleString()} rows of <strong>synthetic</strong> data with only{' '}
            {dataset.distinct_symptom_sets} distinct symptom combinations. High scores here show the model learned this
            dataset&apos;s patterns. They say nothing about accuracy on real patients.
          </p>
        </div>
      </div>

      <section aria-labelledby="metrics-heading">
        <h2 id="metrics-heading" className="mb-3 text-lg font-semibold">Evaluation</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cv && <Metric label="Accuracy (grouped 5-fold CV)" value={percent(cv.accuracy.mean, 1)} detail={`± ${percent(cv.accuracy.std, 1)} over ${cv.folds} folds`} />}
          <Metric label="Macro F1 (hold-out)" value={percent(holdout.f1_macro, 1)} detail={`Precision ${percent(holdout.precision_macro, 1)} · recall ${percent(holdout.recall_macro, 1)}`} />
          <Metric label="Top-3 accuracy (hold-out)" value={percent(holdout.top3_accuracy, 1)} detail="True condition among the three suggestions" />
          <Metric label="Calibration error (ECE)" value={holdout.expected_calibration_error.toFixed(3)} detail="0 = confidence matches accuracy" />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-slate-500">
          {ev.protocol} The original project reported 97.01% from a plain random split. That split lets identical
          symptom sets appear in both train and test ({dataset.duplicate_rows} rows are exact duplicates), and the
          original code also trained on the CSV header as a fake class. The same random split on the corrected data
          gives {percent(ev.random_split_accuracy, 1)}.
        </p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[auto_minmax(0,1fr)]">
        <section className="card min-w-0 p-5" aria-labelledby="cm-heading">
          <h2 id="cm-heading" className="card-title">Confusion matrix (hold-out, n = {holdout.n_test})</h2>
          <p className="mb-4 text-xs text-slate-500">Cell shade is the share of each true condition. Hover a cell for details.</p>
          <ConfusionMatrix labels={holdout.confusion_matrix.labels} matrix={holdout.confusion_matrix.matrix} />
        </section>

        <section className="card min-w-0 overflow-hidden" aria-labelledby="per-class-heading">
          <div className="card-header"><h2 id="per-class-heading" className="card-title">Per-condition results (hold-out)</h2></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr className="border-b border-slate-100">
                  <th scope="col" className="px-5 py-2 text-left font-medium">Condition</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Precision</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Recall</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">F1</th>
                  <th scope="col" className="px-5 py-2 text-right font-medium">Test rows</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 tabular-nums">
                {Object.entries(holdout.per_class).map(([name, m]) => (
                  <tr key={name}>
                    <th scope="row" className="px-5 py-2 text-left font-medium text-slate-800">{name}</th>
                    <td className="px-3 py-2 text-right">{m.precision.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{m.recall.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{m.f1.toFixed(2)}</td>
                    <td className="px-5 py-2 text-right text-slate-500">{m.support}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-5 py-3 text-xs text-slate-500">Some conditions have very few distinct test cases, so their per-class scores are noisy.</p>
        </section>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <section className="card p-5" aria-labelledby="data-heading">
          <h2 id="data-heading" className="card-title flex items-center gap-2"><Database className="size-4 text-slate-400" aria-hidden /> Training data</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">File</dt><dd className="truncate pl-4 font-medium" title={dataset.file}>{dataset.file}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Rows</dt><dd className="font-medium">{dataset.rows}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Distinct symptom sets</dt><dd className="font-medium">{dataset.distinct_symptom_sets}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Duplicate rows</dt><dd className="font-medium">{dataset.duplicate_rows}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Origin</dt><dd className="font-medium">Synthetic</dd></div>
          </dl>
        </section>
        <section className="card p-5 md:col-span-2" aria-labelledby="vocab-heading">
          <h2 id="vocab-heading" className="card-title flex items-center gap-2"><Layers className="size-4 text-slate-400" aria-hidden /> Vocabulary ({model.symptoms.length} symptoms)</h2>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {model.symptoms.map((s) => <span key={s} className="chip border-slate-200 bg-slate-50 text-slate-700">{s}</span>)}
          </div>
          <p className="hint">Any other symptom is recorded on the appointment but ignored by the model.</p>
        </section>
      </div>

      <section className="card p-5" aria-labelledby="limits-heading">
        <h2 id="limits-heading" className="card-title flex items-center gap-2"><FlaskConical className="size-4 text-slate-400" aria-hidden /> How to read the output</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-600">
          <li><strong>Model confidence</strong> is the share of trees voting for a condition. It measures agreement inside the model, not the chance that a patient has the disease.</li>
          <li>Each training row has 4–5 symptoms. Suggestions made from 1–2 symptoms are less reliable, and the API says so.</li>
          <li>The model only knows these {model.classes.length} conditions. It will always pick one of them, even for a patient who has none of them.</li>
          <li>Symptoms have no severity, duration, age, sex, vital signs or history. A real clinical decision needs all of these.</li>
        </ul>
      </section>
    </div>
  )
}
