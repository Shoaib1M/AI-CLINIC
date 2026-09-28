"""Success-response helpers. Every success body is {"data": ..., "meta"?: ...}."""

from flask import jsonify, request


def ok(data, status: int = 200, meta: dict | None = None):
    body = {"data": data}
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status


def json_body():
    """Parsed JSON body, or None if missing/invalid (validators turn that into a 400)."""
    return request.get_json(silent=True)
