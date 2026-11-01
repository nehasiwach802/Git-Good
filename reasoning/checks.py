"""Presentation metadata for existing checks; no new experimental procedure."""
import hashlib
import json

INPUTS = {
    "instructor_review": "instructor_authorization",
    "confirm_connections": "connection_confirmation",
    "review_wiring": "corrected_circuit",
    "resolve_simulation": "simulation_configuration",
    "record_approved_measurement": "measurement",
    "instructor_supervised_setup_check": "instructor_observation",
    "explain_prediction": "student_explanation",
    "review_learning_objective": "student_explanation",
}


def stable_id(prefix, payload):
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    return prefix + hashlib.sha256(encoded).hexdigest()[:16]


def finish(result):
    check = result["next_check"]
    check["check_id"] = stable_id("check_", check)
    check["input_type"] = INPUTS[check["kind"]]
    check["requires_instructor"] = check["kind"] in {
        "instructor_review", "instructor_supervised_setup_check", "record_approved_measurement"}
    check.setdefault("evidence_ids", [f["id"] for f in result["findings"]])
    return result
