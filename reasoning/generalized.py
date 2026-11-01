"""Format-independent, uncertainty-aware orchestration (request version 2.0)."""
from copy import deepcopy
from .observations import (validate_observation, validate_reference, resolved,
                           object_, text, fail)
from .registry import MODELS, ANALYSES
from .circuit import diff, number
from .checks import finish, stable_id
from .engine import diagnose
from .spice import simulate
from .validation import validate_request


def validate_generalized(request):
    object_(request, "$")
    if request.get("schema_version") != "2.0":
        fail("$.schema_version", "requires 2.0")
    validate_reference(request.get("reference"))
    validate_observation(request.get("observation"))
    mapping = request.get("component_map", {})
    object_(mapping, "$.component_map")
    observed = {c["id"] for c in request["observation"]["components"]}
    reference = {c["id"] for c in request["reference"]["circuit"]["components"]}
    if set(mapping) - observed:
        fail("$.component_map", "mapping names unknown observed components")
    targets = []
    for target in mapping.values():
        if target is not None:
            if not isinstance(target, str) or target not in reference:
                fail("$.component_map", "target must be a reference ID or null for an explicitly extra component")
            targets.append(target)
    if len(set(targets)) != len(targets):
        fail("$.component_map", "identity mapping must be one-to-one")
    if "problem_description" in request and (
            not isinstance(request["problem_description"], str) or len(request["problem_description"]) > 4000):
        fail("$.problem_description", "at most 4000 characters")
    analysis = request["reference"]["analysis"]
    if analysis["engine"] == "analog_ac":
        probes = analysis.get("probes")
        if not isinstance(probes, list) or not 1 <= len(probes) <= 20:
            fail("$.reference.analysis.probes", "requires 1..20 probes")
        ids = set()
        for p in probes:
            object_(p, "$.reference.analysis.probes")
            text(p.get("id"), "$.reference.analysis.probes.id")
            if p["id"] in ids:
                fail("$.reference.analysis.probes", "duplicate probe ID")
            ids.add(p["id"])
            for field in ("positive_port", "negative_port"):
                if not isinstance(p.get(field), str) or p[field] not in request["reference"].get("ports", {}):
                    fail("$.reference.analysis.probes", "probe must name declared reference ports")
            number(p.get("frequency_hz"), "frequency_hz", True)
            for key, default in (("relative_tolerance", .05), ("absolute_tolerance_v", .01)):
                if number(p.get(key, default), key) < 0:
                    fail("$.reference.analysis.probes", "negative tolerance")
        # Reuse the established measurement validator without requiring a
        # supported student topology or assuming the observed nets are complete.
        synthetic = {"components": [{"id": "Vcheck", "type": "V", "pins": {"+": "x", "-": "0"}, "dc": 0, "ac": 1}]}
        validate_request({"schema_version": "1.0", "experiment": {"circuit": synthetic,
            "probes": [{**p, "positive": "x", "negative": "0"} for p in probes]},
            "student_circuit": synthetic, "measurements": request.get("measurements", []),
            "student_expectations": request.get("student_expectations", {}),
            "equipment_evidence": request.get("equipment_evidence", {})})
    elif analysis["engine"] == "7400_as_not":
        if type(analysis.get("gate", 1)) is not int or not 1 <= analysis.get("gate", 1) <= 4:
            fail("$.reference.analysis.gate", "requires gate 1..4")
        if not isinstance(analysis.get("component_id"), str) or analysis["component_id"] not in reference:
            fail("$.reference.analysis.component_id", "requires a reference component ID")
        roles = analysis.get("port_roles", {})
        if (not isinstance(roles, dict) or set(roles) != {"input", "output", "vcc", "gnd"}
                or any(not isinstance(p, str) or p not in request["reference"].get("ports", {}) for p in roles.values())):
            fail("$.reference.analysis.port_roles", "map input/output/vcc/gnd to declared ports")
        for field in ("measurements", "student_expectations"):
            rows = request.get(field, [])
            if not isinstance(rows, list) or len(rows) > 2:
                fail("$." + field, "requires at most two binary rows")
            seen = set()
            for row in rows:
                if (not isinstance(row, dict) or set(row) != {"input", "output"}
                        or any(type(row[k]) is not int or row[k] not in (0, 1) for k in row)):
                    fail("$." + field, "requires integer binary input/output rows")
                if row["input"] in seen:
                    fail("$." + field, "duplicate input condition")
                seen.add(row["input"])
    return request


def prepare(request):
    """Retain primary proposals without replacing them with reference answers."""
    observation = request["observation"]
    mapping = request.get("component_map", {})
    pending = list(observation.get("pending_evidence", []))
    if observation.get("reviewed_revision") != observation["revision"]:
        pending.append("whole_circuit_review")
    if not observation.get("completeness_confirmed", False):
        pending.append("capture_completeness")
    model_gaps = []
    refs = {c["id"]: c for c in request["reference"]["circuit"]["components"]}
    names = {n for c in observation["components"] for p in c["pins"].values()
             for n in [p["net"], *p.get("alternatives", [])] if n is not None}
    names.update(p["net"] for p in observation.get("ports", {}).values() if p["net"] is not None)
    ground_ports = [p for p, n in request["reference"].get("ports", {}).items() if n == "0"]
    ground = None
    for port in ground_ports:
        observed = observation.get("ports", {}).get(port)
        if observed and observed["net"] is not None:
            if ground is not None and observed["net"] != ground:
                pending.append("conflicting_ground_ports")
            ground = observed["net"]
    needs_ground = any(n == "0" for c in request["reference"]["circuit"]["components"] for n in c["pins"].values())
    if needs_ground and (not ground_ports or ground is None):
        pending.append("ground_port_correspondence")
    net_map = {n: ("0" if n == ground else f"obs_{i}") for i, n in enumerate(sorted(names))}
    components = []
    identity_complete = True
    for i, c in enumerate(observation["components"]):
        cid = c["id"]
        # No default identity match based on coincidentally equal labels.
        if cid not in mapping:
            pending.append("identity:" + cid)
            identity_complete = False
            continue
        if not c.get("identity_confirmed", False):
            pending.append("identity:" + cid)
        model = MODELS.get(c["model"])
        if not model:
            model_gaps.append({"kind": "unsupported_model", "model": c["model"], "component": cid})
        properties = c.get("properties", {})
        if model and model.properties:
            if not c.get("properties_confirmed", False) or any(properties.get(p) is None for p in model.properties):
                pending.append("properties:" + cid)
        pins = {}
        for pin, point in c["pins"].items():
            if not resolved(point):
                pending.append(cid + "." + pin)
            if point["net"] is not None:
                pins[pin] = net_map[point["net"]]
        target = mapping[cid]
        if target is None:
            target = f"extra_{i}"
            while target in refs:
                target = "_" + target
        components.append({"id": target, "type": c["model"], "pins": pins,
                           **({p: properties.get(p) for p in model.properties if p in properties} if model else {}),
                           "confirmed": True})
    for port, point in observation.get("ports", {}).items():
        if not resolved(point):
            pending.append("port:" + port)
    for port in request["reference"].get("ports", {}):
        if port not in observation.get("ports", {}):
            pending.append("port:" + port)
    return components, net_map, list(dict.fromkeys(pending)), model_gaps, identity_complete


def diagnose_generalized(request, simulator=simulate):
    validate_generalized(request)
    reference, observation = request["reference"], request["observation"]
    engine = reference["analysis"]["engine"]
    parts, net_map, pending, gaps, identity_complete = prepare(request)
    result = {"schema_version": "2.0", "status": "evaluated", "findings": [], "predictions": [],
              "hypotheses": {k: {"support": "unresolved", "evidence_ids": []} for k in ("wiring", "concept", "apparatus")},
              "reference": {"experiment_id": reference["experiment_id"], "version": reference["version"]},
              "observation": {"id": observation["id"], "revision": observation["revision"]},
              "pending": pending, "capability_gaps": gaps,
              "limitations": ["Unconfirmed extraction differences are not established student wiring faults.",
                              "Confidence labels are not calibrated probabilities; only supported models/analyses can run."]}

    def evidence(kind, certainty, **fields):
        if certainty == "confirmed" and reference["approval"] != "approved":
            certainty = "possible"
        item = {"kind": kind, "certainty": certainty, **fields}
        item["id"] = stable_id("e_", item)
        result["findings"].append(item)
        if certainty == "confirmed":
            result["hypotheses"]["wiring"]["support"] = "supported"
            result["hypotheses"]["wiring"]["evidence_ids"].append(item["id"])

    refs = {c["id"]: c for c in reference["circuit"]["components"]}
    matched = request.get("component_map", {})
    # Values and fixed-directional terminal relationships can be compared even
    # while other parts of the capture remain unresolved.
    terminals = []
    for c in observation["components"]:
        target = matched.get(c["id"])
        if target not in refs:
            continue
        ref = refs[target]
        identity = c.get("identity_confirmed", False)
        if c["model"] != ref["type"]:
            evidence("wrong_type", "confirmed" if identity else "possible", component=c["id"], reference_component=target)
            continue
        model = MODELS.get(c["model"])
        if not model:
            continue
        for pin, point in c["pins"].items():
            if point["net"] is None or point.get("alternatives"):
                evidence("unknown_connection" if point["net"] is None else "alternative_connections",
                         "unresolved" if point["net"] is None else "possible", component=c["id"], pin=pin,
                         proposed_net=point["net"], alternatives=point.get("alternatives", []),
                         evidence_refs=point.get("evidence_refs", []))
        for prop in model.properties:
            value = c.get("properties", {}).get(prop)
            if value is not None and value != ref.get(prop):
                evidence("wrong_property", "confirmed" if identity and c.get("properties_confirmed", False) else "possible",
                         component=c["id"], property=prop, observed=value, expected=ref[prop])
        if not model.interchangeable:
            for pin, point in c["pins"].items():
                if point["net"] is not None:
                    terminals.append((c["id"], pin, ref["pins"][pin], point, identity))
    for name, node in reference.get("ports", {}).items():
        point = observation.get("ports", {}).get(name)
        if point and point["net"] is not None:
            terminals.append(("port:" + name, "tap", node, point, True))
    for i, (a, ap, ar, ao, ai) in enumerate(terminals):
        for b, bp, br, bo, bi in terminals[i + 1:]:
            if (ar == br) != (ao["net"] == bo["net"]):
                certainty = "confirmed" if ai and bi and resolved(ao) and resolved(bo) else "possible"
                evidence("connection_discrepancy", certainty, terminals=[a + "." + ap, b + "." + bp],
                         reference_connected=ar == br, evidence_refs=ao.get("evidence_refs", []) + bo.get("evidence_refs", []))
                if len(result["findings"]) >= 100:
                    break
        if len(result["findings"]) >= 100:
            break
    for c in reference["circuit"]["components"]:
        model = MODELS.get(c["type"])
        if not model:
            gaps.append({"kind": "unsupported_reference_model", "model": c["type"]})
        elif engine in ANALYSES and engine not in model.analyses:
            gaps.append({"kind": "unsupported_model_analysis", "model": c["type"], "engine": engine})
    for c in observation["components"]:
        model = MODELS.get(c["model"])
        if model and engine in ANALYSES and engine not in model.analyses:
            gaps.append({"kind": "unsupported_model_analysis", "model": c["model"], "engine": engine})
    if engine not in ANALYSES:
        gaps.append({"kind": "unsupported_analysis", "engine": engine})
    complete_primary = identity_complete and all(
        len(c["pins"]) == len(MODELS[c["type"]].pins)
        and all(c.get(p) is not None for p in MODELS[c["type"]].properties)
        for c in parts if c["type"] in MODELS)
    if complete_primary and not gaps:
        for finding in diff(reference["circuit"], {"components": parts}):
            evidence(finding.pop("kind"), "confirmed" if not pending else "possible", **finding)
    if reference["approval"] != "approved" or request.get("safety_profile") != "instructor_approved_low_voltage":
        result.update(status="instructor_required", next_check={"kind": "instructor_review", "reason": "Approved reference and workflow required"})
    elif gaps:
        result.update(status="unsupported_analysis", next_check={"kind": "instructor_review", "reason": "Required component model or analysis is unavailable"})
    elif pending:
        result.update(status="needs_confirmation", next_check={"kind": "confirm_connections", "reason": "Resolve observation uncertainty, identity and review before simulation", "items": pending})
    elif engine == "connectivity":
        mismatched = bool(result["hypotheses"]["wiring"]["evidence_ids"])
        result["next_check"] = {"kind": "review_wiring" if mismatched else "review_learning_objective",
                                "reason": "Connectivity comparison complete; no behavioral analysis requested"}
    elif engine == "7400_as_not" and result["hypotheses"]["wiring"]["support"] == "supported":
        result["next_check"] = {"kind": "review_wiring", "reason": "Confirmed topology differs; no ideal logic prediction asserted"}
    else:
        evaluated = RUNNERS[engine](request, parts, net_map, simulator)
        result["predictions"] = evaluated.get("predictions", [])
        result["findings"].extend(evaluated.get("findings", []))
        result["limitations"].extend(evaluated.get("limitations", []))
        for key, value in evaluated["hypotheses"].items():
            if value["support"] == "supported":
                result["hypotheses"][key]["support"] = "supported"
                result["hypotheses"][key]["evidence_ids"].extend(value["evidence_ids"])
        result["next_check"] = evaluated["next_check"]
        # The runner has already finalized its check metadata. Rebuild once.
        for key in ("check_id", "input_type", "requires_instructor"):
            result["next_check"].pop(key, None)
    check_kind = result["next_check"]["kind"]
    configured = [c for c in reference.get("approved_checks", []) if c["kind"] == check_kind]
    if configured and reference["approval"] == "approved":
        result["next_check"]["approved_check"] = deepcopy(configured[0])
    result["next_check"]["evidence_ids"] = [f["id"] for f in result["findings"]]
    return finish(result)


def run_analog(request, components, net_map, simulator):
    reference = request["reference"]
    probes, mapped = [], {}
    for p in reference["analysis"]["probes"]:
        positive, negative = p["positive_port"], p["negative_port"]
        probes.append({**p, "positive": reference["ports"][positive], "negative": reference["ports"][negative]})
        mapped[p["id"]] = {"positive": net_map[request["observation"]["ports"][positive]["net"]],
                            "negative": net_map[request["observation"]["ports"][negative]["net"]]}
    return diagnose({"schema_version": "1.0", "safety_profile": request["safety_profile"],
                     "experiment": {"circuit": reference["circuit"], "probes": probes},
                     "student_circuit": {"components": components}, "student_probe_nodes": mapped,
                     "measurements": request.get("measurements", []),
                     "student_expectations": request.get("student_expectations", {}),
                     "equipment_evidence": request.get("equipment_evidence", {})}, simulator)


def run_logic(request, components, net_map, simulator):
    from labvision.digital import check_not
    reference = request["reference"]
    analysis = reference["analysis"]
    def exported(parts, ports):
        return {"status": "reviewed_connectivity", "components": [{"id": c["id"], "part": c["type"], "pins": c["pins"]} for c in parts],
                "ports": [{"id": role, "role": role, "node": ports[name]} for role, name in analysis["port_roles"].items()]}
    checked_ref = check_not(exported(reference["circuit"]["components"], reference["ports"]), analysis["component_id"], analysis.get("gate", 1))
    if not checked_ref["topology_matches"] or checked_ref["warnings"]:
        fail("$.reference", "reference does not satisfy declared isolated 7400 model")
    observed_ports = {p: net_map[v["net"]] for p, v in request["observation"]["ports"].items()}
    checked = check_not(exported(components, observed_ports), analysis["component_id"], analysis.get("gate", 1))
    result = {"findings": [], "predictions": [], "hypotheses": {k: {"support": "unresolved", "evidence_ids": []} for k in ("wiring", "concept", "apparatus")},
              "limitations": [checked["scope"]] if "scope" in checked else []}
    def finding(kind, **fields):
        f = {"kind": kind, **fields}
        f["id"] = stable_id("e_", f)
        result["findings"].append(f)
        return f["id"]
    if not checked["topology_matches"]:
        for issue in checked["issues"]:
            eid = finding("digital_topology_mismatch", certainty="confirmed", detail=issue)
            result["hypotheses"]["wiring"]["evidence_ids"].append(eid)
        result["hypotheses"]["wiring"]["support"] = "supported"
        check = "review_wiring"
    elif checked["warnings"]:
        for warning in checked["warnings"]:
            finding("undefined_unused_input", detail=warning)
        check = "instructor_supervised_setup_check"
    else:
        table = checked["truth_table"]
        result["predictions"] = [{"probe_id": "logic_truth_table", "reference": {"status": "ok", "truth_table": table}, "student": {"status": "ok", "truth_table": table}}]
        mismatched = False
        expected = {r["input"]: r["output"] for r in request.get("student_expectations", [])}
        for row in request.get("measurements", []):
            prediction = 1 - row["input"]
            match = prediction == row["output"]
            finding("digital_measurement_comparison", input=row["input"], predicted=prediction, measured=row["output"], matches=match)
            mismatched |= not match
            if match and row["input"] in expected and expected[row["input"]] != prediction:
                eid = finding("digital_expectation_disagrees", input=row["input"], expected=expected[row["input"]])
                result["hypotheses"]["concept"]["support"] = "supported"
                result["hypotheses"]["concept"]["evidence_ids"].append(eid)
        check = ("instructor_supervised_setup_check" if mismatched else "record_approved_measurement" if len(request.get("measurements", [])) < 2
                 else "explain_prediction" if result["hypotheses"]["concept"]["support"] == "supported" else "review_learning_objective")
    result["next_check"] = {"kind": check, "reason": "Evaluate supported ideal Boolean behavior and current evidence"}
    return result


RUNNERS = {"analog_ac": run_analog, "7400_as_not": run_logic}
