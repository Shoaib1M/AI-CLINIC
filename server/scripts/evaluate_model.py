"""Evaluate the saved model and compare it with the original project's pipeline.

Usage (from the server/ directory):

    python -m scripts.evaluate_model            # report for the saved artifacts
    python -m scripts.evaluate_model --compare  # also compare baseline vs tuned configs
    python -m scripts.evaluate_model --json     # machine-readable output

Nothing here is written to disk; it only reads the dataset and artifacts.
"""

import argparse
import json
from pathlib import Path

from app.config import BaseConfig
from app.ml.artifacts import load_artifacts
from app.ml.training import (
    MODEL_CONFIGS,
    grouped_cross_validation,
    legacy_pipeline_accuracy,
    load_dataset,
)


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def print_report(report: dict) -> None:
    meta, holdout = report["metadata"], report["metadata"]["evaluation"]["holdout"]
    print(f"\nModel {meta['model_version']}  (trained {meta['trained_at']}, sklearn {meta['sklearn_version']})")
    print(f"Dataset: {meta['dataset']['rows']} rows, {meta['dataset']['distinct_symptom_sets']} distinct "
          f"symptom sets, {meta['dataset']['duplicate_rows']} duplicate rows (synthetic)")

    print("\nGrouped hold-out (no symptom set shared between train and test)")
    for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "top3_accuracy"):
        print(f"  {key:<18} {_pct(holdout[key])}")
    print(f"  {'log_loss':<18} {holdout['log_loss']}")
    print(f"  {'ECE':<18} {holdout['expected_calibration_error']}")

    print("\nPer class")
    print(f"  {'disease':<20}{'precision':>10}{'recall':>10}{'f1':>10}{'support':>9}")
    for disease, m in holdout["per_class"].items():
        print(f"  {disease:<20}{m['precision']:>10.3f}{m['recall']:>10.3f}{m['f1']:>10.3f}{m['support']:>9}")

    cm = holdout["confusion_matrix"]
    short = [label[:6] for label in cm["labels"]]
    print("\nConfusion matrix (rows = true, columns = predicted)")
    print("  " + " " * 20 + "".join(f"{s:>7}" for s in short))
    for label, row in zip(cm["labels"], cm["matrix"]):
        print(f"  {label:<20}" + "".join(f"{v:>7}" for v in row))

    print("\nProtocol comparison (accuracy)")
    legacy = report["legacy_pipeline"]
    print(f"  Original app.py pipeline (header bug + random split): {_pct(legacy['accuracy'])} "
          f"on {legacy['n_test']} rows; classes include {'Disease' in legacy['classes'] and 'the bogus Disease label' or 'no bogus label'}")
    print(f"  Fixed data, random split (duplicates leak):          {_pct(meta['evaluation']['random_split_accuracy'])}")
    print(f"  Fixed data, grouped hold-out (reported):             {_pct(holdout['accuracy'])}")
    cv = meta["evaluation"].get("grouped_cv")
    if cv:
        print(f"  Fixed data, grouped 5-fold CV x3 seeds:              "
              f"{_pct(cv['accuracy']['mean'])} ± {_pct(cv['accuracy']['std'])}")

    if report.get("config_comparison"):
        print("\nConfig comparison (grouped 5-fold CV x3 seeds)")
        for name, res in report["config_comparison"].items():
            print(f"  {name:<9} acc {_pct(res['accuracy']['mean'])} ± {_pct(res['accuracy']['std'])}   "
                  f"F1 {_pct(res['f1_macro']['mean'])}   log loss {res['log_loss']['mean']}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=BaseConfig.DATASET_PATH)
    parser.add_argument("--models", type=Path, default=BaseConfig.MODEL_DIR)
    parser.add_argument("--compare", action="store_true", help="grouped CV for every config")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    _, _, metadata = load_artifacts(args.models)
    dataset = load_dataset(args.dataset)
    if dataset.sha256 != metadata["dataset"]["sha256"]:
        print("WARNING: dataset has changed since the model was trained; retrain it.")

    report = {"metadata": metadata, "legacy_pipeline": legacy_pipeline_accuracy(args.dataset)}
    if args.compare:
        report["config_comparison"] = {name: grouped_cross_validation(dataset, name) for name in MODEL_CONFIGS}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
