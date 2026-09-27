"""Offline training and evaluation pipeline.

    dataset CSV -> normalise symptoms -> MultiLabelBinarizer -> RandomForest
                -> grouped hold-out + grouped cross-validation -> save artifacts

This module is only used by `scripts/train_model.py` and
`scripts/evaluate_model.py`. The web application never trains; it only loads
the saved artifacts (see `predictor.py`).

Why *grouped* evaluation: the dataset has 1,000 rows but only 338 distinct
symptom combinations (167 rows are exact duplicates). A plain random split puts
copies of the same combination in both train and test, so the test score partly
measures memorisation. Grouping by symptom set keeps every combination entirely
on one side of the split.
"""

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.preprocessing import MultiLabelBinarizer

from .preprocessing import normalize_symptoms

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

# "baseline" reproduces the hyper-parameters of the original project and is the
# deployed default. "tuned" is kept for comparison: in grouped CV it scores
# ~0.8pp higher accuracy (inside one standard deviation) but with worse log loss,
# so it is not a clear improvement. See docs/ML.md.
MODEL_CONFIGS = {
    "baseline": {"n_estimators": 200},
    "tuned": {"n_estimators": 300, "min_samples_leaf": 2, "class_weight": "balanced"},
}


@dataclass
class Dataset:
    symptoms: list[list[str]]
    labels: np.ndarray
    frame: pd.DataFrame
    symptom_columns: list[str]
    prescription_columns: list[str]
    sha256: str

    @property
    def groups(self) -> np.ndarray:
        """One group id per distinct (unordered) symptom combination."""
        return np.array(["|".join(sorted(s)) for s in self.symptoms])


def load_dataset(path: Path) -> Dataset:
    path = Path(path)
    frame = pd.read_csv(path)  # the CSV has a header row
    symptom_cols = [c for c in frame.columns if c.lower().startswith("symptom")]
    prescription_cols = [c for c in frame.columns if c.lower().startswith("prescription")]
    if "Disease" not in frame.columns or not symptom_cols:
        raise ValueError(f"{path} must have a 'Disease' column and 'Symptom N' columns")

    symptoms = [normalize_symptoms(row) for row in frame[symptom_cols].itertuples(index=False)]
    keep = [bool(s) and pd.notna(d) for s, d in zip(symptoms, frame["Disease"])]
    frame = frame.loc[keep].reset_index(drop=True)
    symptoms = [s for s, k in zip(symptoms, keep) if k]
    labels = frame["Disease"].astype(str).str.strip().to_numpy()

    return Dataset(
        symptoms=symptoms,
        labels=labels,
        frame=frame,
        symptom_columns=symptom_cols,
        prescription_columns=prescription_cols,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def reference_treatments(dataset: Dataset, top_n: int = 3) -> dict[str, list[str]]:
    """Most frequent treatments recorded per disease in the dataset.

    Same logic as the original `get_top_prescriptions`, computed once at
    training time instead of on every request. Diseases whose rows have no
    treatments recorded get an empty list (5 of the 10 in the current CSV).
    """
    result = {}
    for disease in sorted(set(dataset.labels)):
        rows = dataset.frame.loc[dataset.labels == disease, dataset.prescription_columns]
        values = [str(v).strip() for v in rows.to_numpy().ravel() if pd.notna(v) and str(v).strip()]
        result[disease] = [name for name, _ in Counter(values).most_common(top_n)]
    return result


def build_model(config: str = "baseline") -> RandomForestClassifier:
    return RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, **MODEL_CONFIGS[config])


def grouped_holdout_indices(dataset: Dataset, seed: int = RANDOM_STATE):
    """~80/20 split, stratified by disease, with no symptom set on both sides."""
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    return next(splitter.split(np.zeros(len(dataset.labels)), dataset.labels, dataset.groups))


def expected_calibration_error(probabilities: np.ndarray, y_true, classes, bins: int = 10) -> float:
    """Gap between top-class confidence and actual accuracy, averaged over bins."""
    confidences = probabilities.max(axis=1)
    predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
    correct = predicted == np.asarray(y_true)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (confidences > low) & (confidences <= high)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidences[mask].mean())
    return float(ece)


def top_k_accuracy(probabilities: np.ndarray, y_true, classes, k: int = 3) -> float:
    classes = np.asarray(classes)
    top = np.argsort(-probabilities, axis=1)[:, :k]
    return float(np.mean([label in classes[row] for label, row in zip(y_true, top)]))


def evaluate(model, X_test, y_test) -> dict:
    """Standard classification metrics for a fitted model on a test set."""
    y_pred = model.predict(X_test)
    proba = model.predict_proba(X_test)
    labels = [str(c) for c in model.classes_]
    macro = precision_recall_fscore_support(y_test, y_pred, average="macro", zero_division=0)
    weighted = precision_recall_fscore_support(y_test, y_pred, average="weighted", zero_division=0)
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)

    return {
        "n_test": int(len(y_test)),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(macro[0]), 4),
        "recall_macro": round(float(macro[1]), 4),
        "f1_macro": round(float(macro[2]), 4),
        "f1_weighted": round(float(weighted[2]), 4),
        "top3_accuracy": round(top_k_accuracy(proba, y_test, model.classes_, k=3), 4),
        "log_loss": round(float(log_loss(y_test, proba, labels=model.classes_)), 4),
        "expected_calibration_error": round(expected_calibration_error(proba, y_test, model.classes_), 4),
        "per_class": {
            label: {
                "precision": round(report[label]["precision"], 4),
                "recall": round(report[label]["recall"], 4),
                "f1": round(report[label]["f1-score"], 4),
                "support": int(report[label]["support"]),
            }
            for label in labels
        },
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        },
    }


def grouped_cross_validation(dataset: Dataset, config: str = "baseline", seeds=(0, 1, 2)) -> dict:
    """Repeated 5-fold StratifiedGroupKFold. Returns mean/std of key metrics."""
    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(dataset.symptoms)
    y = dataset.labels
    scores = {"accuracy": [], "f1_macro": [], "log_loss": []}
    for seed in seeds:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for train_idx, test_idx in splitter.split(X, y, dataset.groups):
            model = build_model(config).fit(X[train_idx], y[train_idx])
            m = evaluate(model, X[test_idx], y[test_idx])
            for key in scores:
                scores[key].append(m[key])
    return {
        "folds": len(scores["accuracy"]),
        **{
            key: {"mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v)), 4)}
            for key, v in scores.items()
        },
    }


def random_split_accuracy(dataset: Dataset, config: str = "baseline") -> float:
    """The original project's protocol (plain random 80/20 split) on the fixed data.

    Reported only for comparison; duplicated symptom sets make it optimistic.
    """
    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(dataset.symptoms)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, dataset.labels, test_size=0.2, random_state=RANDOM_STATE
    )
    model = build_model(config).fit(X_tr, y_tr)
    return round(float(accuracy_score(y_te, model.predict(X_te))), 4)


def legacy_pipeline_accuracy(path: Path) -> dict:
    """Reproduce the pre-refactor app.py pipeline exactly, including its bug.

    app.py read the CSV with `header=None`, so the header line became a
    training row labelled "Disease" with symptoms "symptom 1".."symptom 5".
    This reproduces the 97.01% figure quoted in the old README.
    """
    frame = pd.read_csv(path, header=None)
    frame.columns = [f"Symptom_{i}" for i in range(1, 6)] + ["Disease"] + [
        f"Prescription_{i}" for i in range(1, 4)
    ]
    cols = [f"Symptom_{i}" for i in range(1, 6)]
    symptoms = frame[cols].apply(
        lambda row: [str(s).strip().lower() for s in row if pd.notna(s) and str(s).strip()], axis=1
    )
    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(symptoms)
    X_tr, X_te, y_tr, y_te = train_test_split(X, frame["Disease"], test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=200, random_state=42).fit(X_tr, y_tr)
    return {
        "accuracy": round(float(accuracy_score(y_te, model.predict(X_te))), 4),
        "n_test": int(len(y_te)),
        "classes": sorted(str(c) for c in model.classes_),
    }


def train(dataset_path: Path, config: str = "baseline", run_cv: bool = True):
    """Full pipeline. Returns (model, mlb, metadata); the caller saves them."""
    dataset = load_dataset(dataset_path)
    logger.info("dataset_loaded", extra={"rows": len(dataset.labels), "sha256": dataset.sha256[:12]})

    # 1. Honest evaluation on a grouped hold-out set.
    mlb_eval = MultiLabelBinarizer()
    X_all = mlb_eval.fit_transform(dataset.symptoms)
    train_idx, test_idx = grouped_holdout_indices(dataset)
    eval_model = build_model(config).fit(X_all[train_idx], dataset.labels[train_idx])
    holdout = evaluate(eval_model, X_all[test_idx], dataset.labels[test_idx])
    holdout["n_train"] = int(len(train_idx))

    cv = grouped_cross_validation(dataset, config) if run_cv else None

    # 2. Final model: refit on all rows so no data is wasted once evaluated.
    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(dataset.symptoms)
    model = build_model(config).fit(X, dataset.labels)
    model.n_jobs = None  # inference is single-row; avoid spinning up worker pools

    trained_at = datetime.now(timezone.utc)
    distribution = Counter(dataset.labels.tolist())
    metadata = {
        "model_version": f"rf-{config}-{trained_at:%Y%m%d}-{dataset.sha256[:8]}",
        "trained_at": trained_at.isoformat(timespec="seconds"),
        "algorithm": "RandomForestClassifier",
        "config": config,
        "hyperparameters": {"random_state": RANDOM_STATE, **MODEL_CONFIGS[config]},
        "sklearn_version": sklearn.__version__,
        "dataset": {
            "file": Path(dataset_path).name,
            "sha256": dataset.sha256,
            "rows": len(dataset.labels),
            "distinct_symptom_sets": int(len(set(dataset.groups))),
            "duplicate_rows": int(dataset.frame.duplicated().sum()),
            "class_distribution": dict(sorted(distribution.items())),
            "synthetic": True,
        },
        "features": [str(c) for c in mlb.classes_],
        "classes": [str(c) for c in model.classes_],
        "reference_treatments": reference_treatments(dataset),
        "evaluation": {
            "protocol": (
                "Grouped hold-out: StratifiedGroupKFold (5 folds, first fold as test), "
                "grouped by unordered symptom set so no combination appears in both "
                "train and test. Final model is refit on all rows afterwards."
            ),
            "holdout": holdout,
            "grouped_cv": cv,
            "random_split_accuracy": random_split_accuracy(dataset, config),
        },
    }
    return model, mlb, metadata
