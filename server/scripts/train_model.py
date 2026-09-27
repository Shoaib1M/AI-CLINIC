"""Train the disease classifier and write the artifacts the API loads.

Usage (from the server/ directory):

    python -m scripts.train_model                   # baseline config, default paths
    python -m scripts.train_model --config tuned    # alternative hyper-parameters
    python -m scripts.train_model --no-cv           # skip cross-validation (faster)
"""

import argparse
import json
import logging
from pathlib import Path

from app.config import BaseConfig
from app.logging_config import configure_logging
from app.ml.artifacts import save_artifacts
from app.ml.training import MODEL_CONFIGS, train


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=BaseConfig.DATASET_PATH)
    parser.add_argument("--output", type=Path, default=BaseConfig.MODEL_DIR, help="artifact directory")
    parser.add_argument("--config", choices=sorted(MODEL_CONFIGS), default="baseline")
    parser.add_argument("--no-cv", action="store_true", help="skip grouped cross-validation")
    args = parser.parse_args()

    configure_logging("INFO")
    log = logging.getLogger("train_model")

    model, mlb, metadata = train(args.dataset, config=args.config, run_cv=not args.no_cv)
    save_artifacts(model, mlb, metadata, args.output)

    ev = metadata["evaluation"]
    summary = {
        "model_version": metadata["model_version"],
        "holdout_accuracy": ev["holdout"]["accuracy"],
        "holdout_f1_macro": ev["holdout"]["f1_macro"],
        "holdout_top3_accuracy": ev["holdout"]["top3_accuracy"],
        "grouped_cv_accuracy": ev["grouped_cv"]["accuracy"] if ev["grouped_cv"] else None,
        "random_split_accuracy (optimistic)": ev["random_split_accuracy"],
    }
    log.info("model_saved", extra={"output": str(args.output)})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
