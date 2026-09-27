"""Symptom normalisation shared by training and inference.

Using exactly the same function on both sides is what keeps the feature space
consistent: "Body Ache ", "body  ache" and "body_ache" all map to the column
the MultiLabelBinarizer learned as "body ache".
"""

import re
from collections.abc import Iterable

# Conservative aliases: only spelling/plural variants of symptoms that already
# exist in the dataset vocabulary. Anything clinically ambiguous (for example
# "stuffy nose" vs "congestion") is intentionally NOT mapped.
SYMPTOM_ALIASES = {
    "body aches": "body ache",
    "bodyache": "body ache",
    "headaches": "headache",
    "joint pains": "joint pain",
    "chill": "chills",
    "sore throats": "sore throat",
    "itchy eye": "itchy eyes",
    "sneeze": "sneezing",
    "breathlessness": "shortness of breath",
    "short of breath": "shortness of breath",
    "vomit": "vomiting",
    "rashes": "rash",
    "tired": "fatigue",
    "tiredness": "fatigue",
    "dizzy": "dizziness",
    "loss of apetite": "loss of appetite",
}

_WHITESPACE = re.compile(r"\s+")
_SEPARATORS = re.compile(r"[_\-]+")


def normalize_symptom(raw) -> str | None:
    """Return the canonical form of one symptom, or None if it is empty."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text or text == "nan":
        return None
    text = _SEPARATORS.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return SYMPTOM_ALIASES.get(text, text) or None


def normalize_symptoms(raw_symptoms: Iterable) -> list[str]:
    """Normalise a collection of symptoms, dropping blanks and duplicates (order kept)."""
    seen: dict[str, None] = {}
    for raw in raw_symptoms:
        symptom = normalize_symptom(raw)
        if symptom:
            seen.setdefault(symptom, None)
    return list(seen)
