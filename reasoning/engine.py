"""Evidence ledger: ordinal support, never fabricated probabilities."""
from .circuit import normalize, diff, number, token
from .spice import simulate
from .validation import validate_request
from .checks import stable_id, finish
from copy import deepcopy


def diagnose(request, simulator=simulate):
    validate_request(request)
    if request.get("schema_version") != "1.0":
        raise ValueError("schema_version must be 1.0")
    experiment = request["experiment"]
    reference = normalize(experiment["circuit"])
    student = normalize(request["student_circuit"])
    probes = experiment["probes"]
    if not isinstance(probes, list) or not 1 <= len(probes) <= 20:
        raise ValueError("require 1..20 probes")
    ids = [token(p["id"]) for p in probes]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate probe IDs")
    measurements = request.get("measurements", [])
    if len({m["probe_id"] for m in measurements}) != len(measurements):
        raise ValueError("duplicate measurements")
    for m in measurements:
        if m["probe_id"] not in ids or m.get("unit") != "V" or m.get("convention") != "ac_magnitude":
            raise ValueError("measurement requires known probe, V, ac_magnitude")
        if number(m["value"], "measurement") < 0:
            raise ValueError("AC magnitude cannot be negative")
    unknown = [c["id"] for c in student["components"] if not c["confirmed"]]
    result = {"schema_version": "1.0", "findings": [], "predictions": [],
              "hypotheses": {k: {"support": "unresolved", "evidence_ids": []}
                             for k in ("wiring", "concept", "apparatus")},
              "limitations": ["Scores are ordinal evidence labels, not probabilities.",
                              "AC magnitude only; ideal op-amp model excludes clipping and supply faults."]}
    if "source_context" in request:
        result["source_context"] = deepcopy(request["source_context"])

    def evidence(kind, **fields):
        eid = stable_id("e_", {"kind": kind, **fields})
        result["findings"].append({"id": eid, "kind": kind, **fields})
        return eid

    def support(kind, eid):
        result["hypotheses"][kind]["support"] = "supported"
        result["hypotheses"][kind]["evidence_ids"].append(eid)

    if request.get("safety_profile") != "instructor_approved_low_voltage":
        result["status"] = "instructor_required"
        result["next_check"] = {"kind": "instructor_review", "reason": "Approved low-voltage workflow required"}
        return finish(result)
    source = request.get("source_context")
    if source and source["candidate_revision"] != source["reviewed_revision"]:
        result["status"] = "needs_confirmation"
        result["next_check"] = {"kind": "confirm_connections",
                                "reason": "Circuit revision changed after review; confirm the current circuit",
                                "candidate_revision": source["candidate_revision"],
                                "reviewed_revision": source["reviewed_revision"]}
        return finish(result)
    if unknown:
        result["status"] = "needs_confirmation"
        result["next_check"] = {"kind": "confirm_connections", "components": unknown,
                                "reason": "Unconfirmed topology cannot support diagnosis"}
        return finish(result)
    differences = diff(reference, student)
    for d in differences:
        eid = evidence(**d)
        result["hypotheses"]["wiring"]["support"] = "supported"
        result["hypotheses"]["wiring"]["evidence_ids"].append(eid)
    mismatches, failures = [], []
    for p in probes:
        relative = number(p.get("relative_tolerance", .05), "relative tolerance")
        absolute = number(p.get("absolute_tolerance_v", .01), "absolute tolerance")
        if relative < 0 or absolute < 0:
            raise ValueError("tolerances cannot be negative")
        ref_prediction = simulator(reference, p)
        # Student probe names must be explicit: renamed nets need corresponding mapping.
        node_override = request.get("student_probe_nodes", {}).get(p["id"], {})
        if set(node_override) - {"positive", "negative"}:
            raise ValueError("student_probe_nodes can override node names only")
        student_probe = {**p, **node_override}
        actual_prediction = simulator(student, student_probe)
        result["predictions"].append({"probe_id": p["id"], "reference": ref_prediction,
                                      "student": actual_prediction})
        if ref_prediction["status"] != "ok":
            failures.append(evidence("simulation_unresolved", probe_id=p["id"],
                                     circuit="reference", status=ref_prediction["status"]))
        if actual_prediction["status"] != "ok":
            failures.append(evidence("simulation_unresolved", probe_id=p["id"],
                                     circuit="student", status=actual_prediction["status"]))
            continue
        m = next((m for m in measurements if m["probe_id"] == p["id"]), None)
        if m is None:
            continue
        predicted = actual_prediction["value"]
        tolerance = number(max(absolute, abs(predicted) * relative), "computed tolerance")
        residual = abs(m["value"] - predicted)
        eid = evidence("measurement_comparison", probe_id=p["id"], predicted=predicted,
                       measured=m["value"], tolerance=tolerance, residual=residual,
                       matches=residual <= tolerance)
        if residual > tolerance:
            mismatches.append(eid)
        expected = request.get("student_expectations", {}).get(p["id"])
        if expected is not None:
            expected = number(expected, "student expectation")
            if residual <= tolerance and abs(expected - predicted) > tolerance:
                support("concept", evidence("expectation_disagrees", probe_id=p["id"],
                                            expected=expected, comparison_evidence=eid))
    # Equipment evidence is supplied by ML3; repeated anomalies alone aren't confirmation.
    equipment = request.get("equipment_evidence", {})
    if not differences and not failures and mismatches and equipment.get("anomaly_follows_equipment") is True:
        source_ids = equipment.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids or not all(isinstance(s, str) for s in source_ids):
            raise ValueError("equipment evidence requires source_ids")
        support("apparatus", evidence("equipment_substitution", source_ids=source_ids,
                                      comparison_evidence=mismatches))
    if differences:
        check = {"kind": "review_wiring", "reason": "Resolve confirmed circuit discrepancies first"}
    elif failures:
        check = {"kind": "resolve_simulation", "reason": "Prediction unavailable; no apparatus attribution", "evidence_ids": failures}
    elif len(measurements) < len(probes):
        check = {"kind": "record_approved_measurement", "reason": "Missing observation at an approved probe"}
    elif mismatches:
        check = {"kind": "instructor_supervised_setup_check", "reason": "Verify values, source and instrument settings; consider approved substitution", "evidence_ids": mismatches}
    elif result["hypotheses"]["concept"]["support"] == "supported":
        check = {"kind": "explain_prediction", "reason": "Ask student to explain the expected circuit response"}
    else:
        check = {"kind": "review_learning_objective", "reason": "Available readings agree; no physical fault established"}
    result.update(status="evaluated", next_check=check)
    return finish(result)
