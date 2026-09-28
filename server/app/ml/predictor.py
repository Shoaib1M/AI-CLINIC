"""Inference: symptoms in, ranked disease suggestions out.

The model's `predict_proba` for a random forest is the average, over all
trees, of the class distribution in the leaf the input lands in. It measures
how strongly the trees agree on this input. It is *not* a calibrated
probability of disease and must never be presented as clinical certainty.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .artifacts import load_artifacts
from .preprocessing import normalize_symptoms

# The dataset has 4–5 symptoms per row, so inputs with very few recognised
# symptoms are outside what the model was trained on.
MIN_RECOMMENDED_SYMPTOMS = 3
MAX_TOP_K = 10


class NoKnownSymptomsError(ValueError):
    """None of the provided symptoms are in the model's vocabulary."""

    def __init__(self, unknown: list[str]):
        super().__init__("None of the provided symptoms are recognised by the model.")
        self.unknown = unknown


@dataclass(frozen=True)
class RankedDisease:
    disease: str
    probability: float


@dataclass(frozen=True)
class PredictionResult:
    prediction: str
    confidence: float
    confidence_level: str
    top_predictions: list[RankedDisease]
    recognized_symptoms: list[str]
    unknown_symptoms: list[str]
    reference_treatments: list[str]
    model_version: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def confidence_level(confidence: float) -> str:
    """Bucket the tree-agreement score into a coarse, human-readable label."""
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "moderate"
    return "low"


class DiseasePredictor:
    def __init__(self, model, mlb, metadata: dict):
        self._model = model
        self._mlb = mlb
        self.metadata = metadata
        self._vocabulary = frozenset(str(s) for s in mlb.classes_)
        self._treatments = metadata.get("reference_treatments", {})

    @classmethod
    def from_directory(cls, model_dir: Path) -> "DiseasePredictor":
        return cls(*load_artifacts(model_dir))

    @property
    def version(self) -> str:
        return self.metadata.get("model_version", "unknown")

    @property
    def known_symptoms(self) -> list[str]:
        return sorted(self._vocabulary)

    @property
    def classes(self) -> list[str]:
        return [str(c) for c in self._model.classes_]

    def reference_treatments(self, disease: str) -> list[str]:
        return list(self._treatments.get(disease, []))

    def split_symptoms(self, symptoms) -> tuple[list[str], list[str]]:
        normalized = normalize_symptoms(symptoms)
        known = [s for s in normalized if s in self._vocabulary]
        unknown = [s for s in normalized if s not in self._vocabulary]
        return known, unknown

    def predict(self, symptoms, top_k: int = 3) -> PredictionResult:
        known, unknown = self.split_symptoms(symptoms)
        if not known:
            raise NoKnownSymptomsError(unknown)

        features = self._mlb.transform([known])
        probabilities = self._model.predict_proba(features)[0]

        top_k = max(1, min(top_k, MAX_TOP_K, len(probabilities)))
        # Sort by probability desc, then by class name for deterministic ties.
        order = sorted(range(len(probabilities)), key=lambda i: (-probabilities[i], self.classes[i]))
        ranked = [
            RankedDisease(self.classes[i], round(float(probabilities[i]), 4)) for i in order[:top_k]
        ]
        best = ranked[0]

        warnings = []
        if unknown:
            warnings.append(
                f"{len(unknown)} symptom(s) not recognised by the model and ignored: {', '.join(unknown)}."
            )
        if len(known) < MIN_RECOMMENDED_SYMPTOMS:
            warnings.append(
                f"Only {len(known)} recognised symptom(s). The model was trained on 4–5 symptoms "
                "per case, so this suggestion is less reliable."
            )

        return PredictionResult(
            prediction=best.disease,
            confidence=best.probability,
            confidence_level=confidence_level(best.probability),
            top_predictions=ranked,
            recognized_symptoms=known,
            unknown_symptoms=unknown,
            reference_treatments=self.reference_treatments(best.disease),
            model_version=self.version,
            warnings=warnings,
        )

