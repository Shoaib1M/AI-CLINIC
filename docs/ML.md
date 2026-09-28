# Machine learning: how the symptom classifier works

> **Scope.** The model is an educational decision-support component trained on a small **synthetic** dataset. It is not a diagnostic device and has not been clinically validated. The numbers below measure how well it learned *this dataset*. They say nothing about accuracy on real patients.

```
Dataset (CSV)
  ↓  load with its header row, drop empty cells
Preprocessing          normalize_symptom(): lower-case, trim, "_"/"-" → space, aliases
  ↓
MultiLabelBinarizer    list of symptoms → 0/1 vector over 21 known symptoms
  ↓
Feature matrix X       1000 × 21  (labels y: 10 conditions)
  ↓
Random forest          200 trees, Gini splits, bootstrap samples, random_state=42
  ↓
Evaluation             grouped hold-out + repeated grouped 5-fold CV
  ↓
Artifacts              models/disease_model.joblib, mlb.joblib, model_metadata.json
  ↓ (offline above / online below)
API startup            load + validate artifacts once per process
  ↓
Prediction request     same normalisation → vector → predict_proba → top-k
```

Code map:

| Step | File |
| --- | --- |
| Normalisation (shared by training and inference) | `server/app/ml/preprocessing.py` |
| Dataset loading, training, evaluation | `server/app/ml/training.py` |
| Artifact save/load and integrity checks | `server/app/ml/artifacts.py` |
| Inference (`DiseasePredictor`) | `server/app/ml/predictor.py` |
| Load once at startup, API use-cases | `server/app/services/prediction_service.py` |
| CLIs | `server/scripts/train_model.py`, `server/scripts/evaluate_model.py` |

## 1. Dataset

`data/updated_synthetic_medical_dataset.csv`, as supplied with the original project:

| Property | Value |
| --- | --- |
| Rows | 1,000 |
| Columns | `Symptom 1`–`Symptom 5`, `Disease`, `Prescription 1`–`Prescription 3` |
| Symptoms per row | 5 (745 rows) or 4 (255 rows) |
| Symptom vocabulary | 21 |
| Conditions | 10: Allergic Rhinitis, COVID-19, Common Cold, Dengue, Gastroenteritis, Influenza, Malaria, Migraine, Pneumonia, Sinusitis |
| Class sizes | 86 (Sinusitis) to 124 (Dengue), so mildly imbalanced |
| Distinct symptom combinations | **338** |
| Exact duplicate rows | **167** |
| Combinations that map to more than one disease | 6 |
| Rows with treatments recorded | 509 (5 of 10 conditions have none) |

The data is synthetic. Every row is a clean set of 4–5 textbook symptoms, with no severity, duration, demographics, vitals or history. Real presentations are messier.

## 2. Preprocessing and the bug that was fixed

The original `app.py` read the CSV with `pd.read_csv(..., header=None)`. The file **has** a header row, so the line `Symptom 1,…,Disease,…` became a training example: a fake condition called `"Disease"` with symptoms `"symptom 1"` … `"symptom 5"`. The committed `disease_model.joblib` contained that class and those five features. The rewrite reads the header properly, and regression tests (`test_dataset_loaded_with_header`, `test_model_card_is_public`) assert the fake class is gone.

The rewrite also moves normalisation into one function, `normalize_symptom()`, used by both training and inference:

- lower-case and trim, turn `_` and `-` into spaces, collapse repeated spaces
- apply a small, conservative alias table of spelling and plural variants only, e.g. `body aches → body ache`, `vomit → vomiting`, `breathlessness → shortness of breath`. Clinically ambiguous mappings (e.g. "stuffy nose" → "congestion") are intentionally **not** made.
- de-duplicate while keeping order

Using the same function on both sides is what keeps training and serving consistent.

## 3. MultiLabelBinarizer → feature matrix

Each patient has a *set* of symptoms of varying size. `MultiLabelBinarizer` learns the vocabulary V (21 symptoms, sorted) and turns a set S into a binary vector:

```
x_j = 1  if V_j ∈ S  else 0          x ∈ {0,1}^21
```

`["fever", "cough", "fatigue"]` has three 1s, one at each of those columns. Symptom order does not matter, which is what we want. The fitted binarizer is saved (`mlb.joblib`), so inference uses exactly the training columns.

**Unknown symptoms.** A symptom outside V has no column. The old code relied on `mlb.transform` silently ignoring it, with a warning in the server log. Now `DiseasePredictor.split_symptoms()` separates known from unknown explicitly:

- Some unknown: they are ignored, returned in `unknown_symptoms`, and a warning is added.
- All unknown: no prediction is made. The API returns `422 NO_KNOWN_SYMPTOMS`; when booking, the appointment is still created and the prediction is recorded as `no_known_symptoms`.

## 4. Random forest

`RandomForestClassifier(n_estimators=200, random_state=42)` is the original project's configuration, kept on purpose (see §7).

- Each of the 200 trees is trained on a **bootstrap sample** (rows drawn with replacement) of the training data.
- At every split, a tree considers a random subset of √21 ≈ 4 features and picks the split that most reduces **Gini impurity**, `G = 1 − Σ_c p_c²`, where `p_c` is the share of class c in the node.
- Trees grow until their leaves are pure (default settings).

Bootstrapping plus random feature subsets make the trees disagree in useful ways, and averaging them reduces variance compared with a single deep tree. For binary features like these, a forest learns combinations such as "chills AND vomiting AND NOT cough".

## 5. Prediction and top-k

```
p(c | x) = (1/T) · Σ_t  p_t(c | leaf_t(x))          T = 200 trees
```

`predict_proba` averages, over trees, the class shares in the leaf each tree sends `x` to. The API sorts the classes by this score (ties broken by name, so results are deterministic) and returns the top `k` (default 3). The first entry is the `prediction`, and its score is the `confidence`.

## 6. Confidence: what it is and is not

`confidence` is **tree agreement**: how consistently this ensemble, trained on this data, votes for one class. It is not the probability that a patient has the disease, for three reasons:

1. **No clinical prior.** Class frequencies in a synthetic CSV are not disease prevalence in a clinic.
2. **Closed world.** The model can only choose among 10 conditions. For a patient with something else it will still pick one, sometimes with high agreement.
3. **Calibration.** On the grouped hold-out set, the mean top confidence is **0.81** while accuracy is **0.974**, an expected calibration error (ECE) of **0.164**. On this data the forest is *under*-confident. The number is still useful for ranking, but it does not match observed frequencies.

The UI therefore says "model confidence" everywhere, shows the top 3 rather than one answer, buckets the score (`high` ≥ 0.7, `moderate` ≥ 0.4, `low`), and warns when there are fewer than 3 recognised symptoms. Sparse inputs spread the score across several conditions, which is the honest behaviour:

| Input | Top 3 (model confidence) |
| --- | --- |
| fever | COVID-19 0.18, Influenza 0.18, Malaria 0.18 |
| fever, cough | COVID-19 0.29, Pneumonia 0.22, Common Cold 0.14 |
| fever, cough, fatigue, body ache, loss of appetite | COVID-19 0.75, Influenza 0.23, Malaria 0.02 |
| fever, chills, vomiting, nausea | Malaria 0.92, Gastroenteritis 0.06, Influenza 0.01 |

## 7. Evaluation

### Why the old 97.01% was misleading

Reproducing the original pipeline (`legacy_pipeline_accuracy()` in `training.py`) gives **97.01% on 201 test rows**, exactly the old README figure. It has two problems:

1. It includes the fake `"Disease"` row (hence 201 test rows instead of 200).
2. A plain random split puts identical symptom sets in both train and test. With only 338 distinct combinations among 1,000 rows, **76%** of test rows had an exact copy in training, so much of the score measured memorisation.

### Protocol now used

Every row is assigned to a *group* = its unordered symptom set. `StratifiedGroupKFold` keeps each group entirely in train or entirely in test, and keeps class proportions similar.

- **Grouped hold-out**: first of 5 folds, 808 train / 192 test rows. Per-class metrics and the confusion matrix come from this split.
- **Grouped 5-fold CV × 3 seeds** (15 folds): the headline number, because one split of 338 groups is noisy.
- The final deployed model is then refit on all 1,000 rows.

### Results (baseline configuration, from `python -m scripts.evaluate_model`)

| Protocol | Accuracy |
| --- | --- |
| Original pipeline (header bug + random split) | 97.01% |
| Fixed data, random split (duplicates leak) | 95.50% |
| Fixed data, grouped hold-out | 97.40% |
| **Fixed data, grouped 5-fold CV × 3 seeds** | **95.67% ± 2.33%** |

Grouped hold-out, all metrics:

| Metric | Value |
| --- | --- |
| Accuracy | 97.40% |
| Precision (macro) | 95.95% |
| Recall (macro) | 94.96% |
| F1 (macro) | 95.15% |
| Top-3 accuracy | 100.00% |
| Log loss | 0.246 |
| ECE | 0.164 |

Per class (hold-out):

| Condition | Precision | Recall | F1 | Test rows |
| --- | --- | --- | --- | --- |
| Allergic Rhinitis | 1.000 | 1.000 | 1.000 | 18 |
| COVID-19 | 1.000 | 0.917 | 0.957 | 12 |
| Common Cold | 1.000 | 1.000 | 1.000 | 57 |
| Dengue | 0.750 | 1.000 | 0.857 | 6 |
| Gastroenteritis | 1.000 | 0.857 | 0.923 | 7 |
| Influenza | 0.909 | 0.833 | 0.870 | 12 |
| Malaria | 1.000 | 0.889 | 0.941 | 9 |
| Migraine | 0.979 | 1.000 | 0.990 | 47 |
| Pneumonia | 0.957 | 1.000 | 0.978 | 22 |
| Sinusitis | 1.000 | 1.000 | 1.000 | 2 |

Confusion matrix (rows = true, columns = predicted). The 5 errors are Influenza→Dengue (2), COVID-19→Pneumonia, Gastroenteritis→Migraine and Malaria→Influenza: conditions whose synthetic symptom sets overlap (fever, body ache, nausea).

```
                    Allerg COVID- Common Dengue Gastro Influe Malari Migrai Pneumo Sinusi
Allergic Rhinitis       18      0      0      0      0      0      0      0      0      0
COVID-19                 0     11      0      0      0      0      0      0      1      0
Common Cold              0      0     57      0      0      0      0      0      0      0
Dengue                   0      0      0      6      0      0      0      0      0      0
Gastroenteritis          0      0      0      0      6      0      0      1      0      0
Influenza                0      0      0      2      0     10      0      0      0      0
Malaria                  0      0      0      0      0      1      8      0      0      0
Migraine                 0      0      0      0      0      0      0     47      0      0
Pneumonia                0      0      0      0      0      0      0      0     22      0
Sinusitis                0      0      0      0      0      0      0      0      0      2
```

Note the uneven test support (Sinusitis 2, Common Cold 57). Grouping moves whole symptom sets at a time, and some conditions have only a few distinct combinations. Per-class numbers for small classes are noisy. Prefer the CV figure.

### Was the model improved? An honest answer

I compared the original hyper-parameters with a tuned configuration (`n_estimators=300, min_samples_leaf=2, class_weight="balanced"`) using the same repeated grouped CV (`python -m scripts.evaluate_model --compare`):

| Config | Accuracy | Macro F1 | Log loss |
| --- | --- | --- | --- |
| baseline (deployed) | 95.67% ± 2.33% | 93.40% | 0.273 |
| tuned | 96.31% ± 1.65% | 94.18% | 0.306 |

The tuned model gains 0.6 points of accuracy, well inside one standard deviation, and its probabilities get worse (higher log loss). That is not a convincing improvement, so the **original RandomForest configuration is kept**. The real improvements are engineering ones: correct data loading, leak-free evaluation, shared preprocessing, explicit unknown-symptom handling, top-k output, validated artifacts, and no retraining at startup.

Calibration (`CalibratedClassifierCV`) was not applied. With 338 distinct combinations, a calibration split would be tiny and would mostly re-fit this synthetic distribution. The ECE is reported instead, and the UI does not present confidence as a probability.

## 8. Training vs inference

**Training is offline and explicit.**

```bash
cd server
python -m scripts.train_model            # writes models/*.joblib + model_metadata.json (≈10 s)
python -m scripts.train_model --no-cv    # faster; skips cross-validation
python -m scripts.evaluate_model --compare
```

`model_metadata.json` records the model version (`rf-<config>-<date>-<dataset hash>`), training time, scikit-learn version, hyper-parameters, the dataset SHA-256, features, classes, reference treatments and every metric above. `evaluate_model` warns if the CSV has changed since training.

**Inference never trains.** At startup `prediction_service.init_app()` loads the artifacts once per process and validates them:

- all three files exist and deserialize
- the model is a `RandomForestClassifier` and the binarizer is fitted
- `model.n_features_in_ == len(mlb.classes_)`
- the classes and features in the metadata match the objects
- a scikit-learn version mismatch is logged as a warning

If validation fails, the API still starts. Booking works, `/api/predictions` returns 503, and `/api/health` reports `degraded`. The original code retrained silently inside the web process whenever artifacts were missing or failed to load.

The scikit-learn version is pinned (`1.3.2`) because pickled models are only guaranteed to load in the version that wrote them. After upgrading scikit-learn, retrain.

## 9. Reference treatments

The dataset's `Prescription 1–3` columns are summarised at training time, per condition, as the three most frequent values. This is the same logic as the original `get_top_prescriptions()`, but computed once instead of re-reading the CSV on every request. They appear in the UI as "Treatments recorded in the training data: reference only", and the doctor can insert one into a prescription only by clicking it. Five conditions (Allergic Rhinitis, Gastroenteritis, Influenza, Migraine, Sinusitis) have none recorded, and the UI says so rather than inventing any.

## 10. Limitations of symptom-to-disease prediction

- **Synthetic, tiny data.** 338 distinct combinations of 21 symptoms cannot represent real clinical variation.
- **Closed set of 10 conditions.** There is no "none of the above" or "urgent: seek care" output.
- **No context.** Severity, onset, duration, age, sex, comorbidities, vitals, labs, travel history and medication all matter clinically and are all absent.
- **Binary symptoms.** "Mild headache for a month" and "worst headache of my life" are the same feature.
- **Label noise.** Six symptom sets appear with two different diagnoses, so no model can be 100% right on this data.
- **Front-desk input.** Symptoms are typed by non-clinical staff and may be incomplete or imprecise.
- **Overlapping presentations.** Viral and bacterial respiratory infections, dengue and malaria share symptoms, and the confusion matrix shows exactly these mix-ups.

These limitations are why the model's role in the product is intentionally narrow: rank, explain, warn, and leave every decision to the clinician.
