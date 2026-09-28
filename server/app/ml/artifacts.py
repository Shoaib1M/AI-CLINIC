"""Saving and loading model artifacts, with integrity checks.

The deployed model is three files in MODEL_DIR:

    disease_model.joblib   fitted RandomForestClassifier
    mlb.joblib             fitted MultiLabelBinarizer (symptom vocabulary)
    model_metadata.json    version, training data fingerprint, metrics, etc.
"""

import json
import logging
from pathlib import Path

import joblib
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

logger = logging.getLogger(__name__)

MODEL_FILENAME = "disease_model.joblib"
MLB_FILENAME = "mlb.joblib"
METADATA_FILENAME = "model_metadata.json"


class ModelArtifactError(RuntimeError):
    """Raised when model artifacts are missing, corrupt or inconsistent."""


def save_artifacts(model, mlb, metadata: dict, model_dir: Path) -> None:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / MODEL_FILENAME, compress=3)
    joblib.dump(mlb, model_dir / MLB_FILENAME)
    (model_dir / METADATA_FILENAME).write_text(json.dumps(metadata, indent=2) + "\n")


def load_artifacts(model_dir: Path):
    """Load and validate (model, mlb, metadata). Raises ModelArtifactError."""
    model_dir = Path(model_dir)
    paths = {name: model_dir / name for name in (MODEL_FILENAME, MLB_FILENAME, METADATA_FILENAME)}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ModelArtifactError(
            f"Missing model artifact(s) in {model_dir}: {', '.join(missing)}. "
            "Run `python -m scripts.train_model` from the server directory."
        )

    try:
        model = joblib.load(paths[MODEL_FILENAME])
        mlb = joblib.load(paths[MLB_FILENAME])
        metadata = json.loads(paths[METADATA_FILENAME].read_text())
    except Exception as exc:  # corrupt pickle, bad JSON, incompatible library...
        raise ModelArtifactError(f"Could not read model artifacts: {exc}") from exc

    if not isinstance(model, RandomForestClassifier):
        raise ModelArtifactError(f"Expected RandomForestClassifier, got {type(model).__name__}")
    if not isinstance(mlb, MultiLabelBinarizer) or not hasattr(mlb, "classes_"):
        raise ModelArtifactError("mlb.joblib is not a fitted MultiLabelBinarizer")
    if model.n_features_in_ != len(mlb.classes_):
        raise ModelArtifactError(
            f"Feature mismatch: model expects {model.n_features_in_} features, "
            f"binarizer produces {len(mlb.classes_)}"
        )
    if list(metadata.get("classes", [])) != [str(c) for c in model.classes_]:
        raise ModelArtifactError("model_metadata.json classes do not match the model")
    if list(metadata.get("features", [])) != [str(c) for c in mlb.classes_]:
        raise ModelArtifactError("model_metadata.json features do not match the binarizer")

    trained_with = metadata.get("sklearn_version")
    if trained_with and trained_with != sklearn.__version__:
        logger.warning(
            "sklearn_version_mismatch",
            extra={"trained_with": trained_with, "running": sklearn.__version__},
        )

    return model, mlb, metadata
