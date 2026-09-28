import json
import shutil

import pytest

from app.config import BaseConfig
from app.ml import DiseasePredictor, ModelArtifactError, NoKnownSymptomsError, normalize_symptoms
from app.ml.artifacts import METADATA_FILENAME, MODEL_FILENAME, load_artifacts
from app.ml.training import legacy_pipeline_accuracy, load_dataset, reference_treatments, train


@pytest.fixture(scope="module")
def predictor():
    return DiseasePredictor.from_directory(BaseConfig.MODEL_DIR)


@pytest.mark.parametrize(
    "symptoms, expected",
    [
        (["cough", "runny nose", "sneezing", "sore throat", "congestion"], "Common Cold"),
        (["vomiting", "chills", "nausea", "body ache", "fever"], "Malaria"),
        (["sneezing", "itchy eyes", "runny nose", "congestion"], "Allergic Rhinitis"),
        (["headache", "nausea", "blurred vision", "dizziness"], "Migraine"),
    ],
)
def test_known_symptom_combinations(predictor, symptoms, expected):
    assert predictor.predict(symptoms).prediction == expected


def test_prediction_is_deterministic_and_order_independent(predictor):
    a = predictor.predict(["fever", "cough", "fatigue"])
    b = predictor.predict(["fatigue", "FEVER", " cough"])
    assert (a.prediction, a.confidence, a.top_predictions) == (b.prediction, b.confidence, b.top_predictions)
    assert sorted(a.recognized_symptoms) == sorted(b.recognized_symptoms)


def test_top_k_is_ranked_and_bounded(predictor):
    result = predictor.predict(["fever", "cough"], top_k=10)
    probs = [r.probability for r in result.top_predictions]
    assert len(probs) == 10
    assert probs == sorted(probs, reverse=True)
    assert sum(probs) == pytest.approx(1.0, abs=1e-3)
    assert len(predictor.predict(["fever"], top_k=50).top_predictions) == 10


def test_unknown_symptoms(predictor):
    with pytest.raises(NoKnownSymptomsError) as exc:
        predictor.predict(["telepathy"])
    assert exc.value.unknown == ["telepathy"]

    mixed = predictor.predict(["fever", "chills", "telepathy"])
    assert mixed.unknown_symptoms == ["telepathy"]
    assert mixed.recognized_symptoms == ["fever", "chills"]


def test_empty_and_malformed_input(predictor):
    with pytest.raises(NoKnownSymptomsError):
        predictor.predict([])
    with pytest.raises(NoKnownSymptomsError):
        predictor.predict([None, "", "   "])


def test_normalisation():
    assert normalize_symptoms([" Body_Aches ", "body ache", "HEAD-ACHE", None, "", "Sore  Throat"]) == [
        "body ache", "head ache", "sore throat",
    ]


def test_artifacts_are_consistent(predictor):
    meta = predictor.metadata
    assert meta["classes"] == predictor.classes
    assert "Disease" not in predictor.classes
    assert not any(s.startswith("symptom ") for s in predictor.known_symptoms)
    assert len(predictor.known_symptoms) == 21


def test_missing_artifacts_raise(tmp_path):
    with pytest.raises(ModelArtifactError, match="Missing"):
        load_artifacts(tmp_path)


def test_inconsistent_metadata_rejected(tmp_path):
    for name in ("disease_model.joblib", "mlb.joblib", METADATA_FILENAME):
        shutil.copy(BaseConfig.MODEL_DIR / name, tmp_path / name)
    meta = json.loads((tmp_path / METADATA_FILENAME).read_text())
    meta["classes"] = meta["classes"][:-1]
    (tmp_path / METADATA_FILENAME).write_text(json.dumps(meta))
    with pytest.raises(ModelArtifactError, match="classes"):
        load_artifacts(tmp_path)


def test_corrupt_model_rejected(tmp_path):
    for name in ("disease_model.joblib", "mlb.joblib", METADATA_FILENAME):
        shutil.copy(BaseConfig.MODEL_DIR / name, tmp_path / name)
    (tmp_path / MODEL_FILENAME).write_bytes(b"not a pickle")
    with pytest.raises(ModelArtifactError):
        load_artifacts(tmp_path)


def test_dataset_loaded_with_header():
    dataset = load_dataset(BaseConfig.DATASET_PATH)
    assert len(dataset.labels) == 1000
    assert "Disease" not in set(dataset.labels)
    assert len(set(dataset.groups)) == 338


def test_reference_treatments_match_original_lookup():
    treatments = reference_treatments(load_dataset(BaseConfig.DATASET_PATH))
    assert treatments["Malaria"] == ["Chloroquine", "Artemether", "Primaquine"]
    assert treatments["Migraine"] == []  # no treatments recorded for this disease


def test_training_pipeline_produces_valid_model():
    model, mlb, metadata = train(BaseConfig.DATASET_PATH, run_cv=False)
    assert "Disease" not in metadata["classes"]
    assert metadata["dataset"]["rows"] == 1000
    holdout = metadata["evaluation"]["holdout"]
    assert holdout["accuracy"] > 0.85
    assert len(holdout["confusion_matrix"]["matrix"]) == 10
    predictor = DiseasePredictor(model, mlb, metadata)
    assert predictor.predict(["cough", "runny nose", "sneezing", "sore throat"]).prediction == "Common Cold"


def test_legacy_pipeline_reproduces_the_header_bug():
    legacy = legacy_pipeline_accuracy(BaseConfig.DATASET_PATH)
    assert "Disease" in legacy["classes"]
    assert legacy["n_test"] == 201
