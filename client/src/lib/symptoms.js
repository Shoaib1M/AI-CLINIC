// Mirrors server/app/ml/preprocessing.py for display purposes only; the server
// re-normalises everything it receives. Aliases come from GET /api/model.
export function normalizeSymptom(raw, aliases = {}) {
  const text = String(raw ?? '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return aliases[text] || text
}
