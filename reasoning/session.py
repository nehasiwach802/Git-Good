"""Optional backend helper for replayable diagnostic history, without storage.

Callers store the returned state in their own authorized session store. Previous
findings are historical only; current hypotheses are recomputed from current
inputs so a corrected circuit does not inherit stale fault support.
"""
from copy import deepcopy
from .api import diagnose_input, validate_input
from .checks import stable_id
from .spice import simulate


def advance_session(request, state=None, simulator=simulate):
    if isinstance(request, dict) and request.get("schema_version") == "2.0":
        return advance_generalized(request, state, simulator)
    if state is None:
        state = {"version": 1, "snapshots": []}
    if (not isinstance(state, dict) or state.get("version") != 1
            or not isinstance(state.get("snapshots"), list)
            or len(state["snapshots"]) > 100
            or not all(isinstance(s, dict) and isinstance(s.get("input_id"), str)
                       and isinstance(s.get("result"), dict) for s in state["snapshots"])):
        raise ValueError("invalid session state; maximum 100 snapshots")
    validate_input(request)
    is_vision = "analysis" in request
    experiment = request.get("experiment", {"analysis":request.get("analysis"),
                                           "gate":request.get("gate",1),
                                           "component_id":request.get("component_id","U1")})
    experiment_key = stable_id("experiment_", experiment)
    if state.get("experiment_key", experiment_key) != experiment_key:
        raise ValueError("start a new session when the reference experiment changes")
    previous_source = state.get("source_context")
    current_source = request.get("source_context")
    if is_vision:
        candidate = request["candidate"]
        current_source = {"board_id":request["board"]["id"],"candidate_id":candidate["candidate_id"],
                          "candidate_revision":candidate["revision"],"reviewed_revision":candidate["reviewed_revision"]}
    if previous_source is not None and (
            not isinstance(previous_source, dict)
            or not isinstance(previous_source.get("board_id"), str)
            or any(isinstance(previous_source.get(k), bool)
                   or not isinstance(previous_source.get(k), int)
                   or previous_source[k] < 0 for k in ("candidate_revision",))
            or not (previous_source.get("reviewed_revision") is None or
                    type(previous_source["reviewed_revision"]) is int and previous_source["reviewed_revision"] >= 0)):
        raise ValueError("invalid session source context")
    if previous_source:
        if not current_source or previous_source["board_id"] != current_source["board_id"]:
            raise ValueError("start a new session when source board changes; source context cannot be dropped")
        if current_source["candidate_revision"] < previous_source["candidate_revision"]:
            raise ValueError("stale candidate revision; session already contains a newer circuit")
        if previous_source.get("candidate_id") != current_source.get("candidate_id"):
            raise ValueError("start a new session when source candidate identity changes")
    if is_vision:
        # Confirmation can change at the same revision; physical observations
        # cannot. Avoid carrying a previously reviewed topology across edits.
        observations=deepcopy(request["candidate"])
        for key in ("board_confirmed","reviewed_revision","issues"):
            observations.pop(key,None)
        for c in observations["components"]:
            c.pop("identity_confirmed",None);c.pop("value_confirmed",None)
        from labvision.core import endpoints
        for _,point,_ in endpoints(observations):
            point.pop("confirmed",None)
        observations["board_groups"]=request["board"]["groups"]
        observation_id=stable_id("observation_", observations)
        if (previous_source and current_source["candidate_revision"]==previous_source["candidate_revision"]
                and state.get("observation_id",observation_id)!=observation_id):
            raise ValueError("candidate observations changed without incrementing revision")
    result = diagnose_input(request, simulator)
    fingerprint = stable_id("input_", request)
    updated = deepcopy(state)
    updated["experiment_key"] = experiment_key
    if current_source:
        updated["source_context"] = deepcopy(current_source)
    if is_vision:
        updated["observation_id"] = observation_id
    snapshots = updated["snapshots"]
    repeated = bool(snapshots and snapshots[-1].get("input_id") == fingerprint)
    if not repeated or snapshots[-1]["result"] != result:
        if len(snapshots) == 100:
            raise ValueError("session history full; archive before continuing")
        snapshots.append({"input_id": fingerprint, "result": deepcopy(result)})
    return {"result": result, "state": updated, "unchanged_input": repeated}


def advance_generalized(request, state=None, simulator=simulate):
    """Bind internal observation identity/revision and reference/model version."""
    request = validate_input(request)
    if state is None:
        state = {"version": 2, "snapshots": []}
    if (not isinstance(state, dict) or state.get("version") != 2
            or not isinstance(state.get("snapshots"), list) or len(state["snapshots"]) > 100
            or any(not isinstance(s, dict) or not isinstance(s.get("input_id"), str)
                   or not isinstance(s.get("result"), dict) for s in state["snapshots"])):
        raise ValueError("invalid generalized session state")
    from .registry import REGISTRY_VERSION
    reference_key = stable_id("reference_", {"reference": request["reference"], "registry_version": REGISTRY_VERSION})
    if state.get("reference_key", reference_key) != reference_key:
        raise ValueError("start a new session when reference/version/analysis changes")
    obs = request["observation"]
    source_key = stable_id("source_", {"id": obs["id"], "board_id": obs.get("source", {}).get("board_id")})
    if state.get("source_key", source_key) != source_key:
        raise ValueError("start a new session when observation or board identity changes")
    previous_revision = state.get("revision", obs["revision"])
    if type(previous_revision) is not int or obs["revision"] < previous_revision:
        raise ValueError("stale observation revision")
    physical = {"components": [{"id": c["id"], "model": c["model"], "properties": c.get("properties", {}),
                   "pins": {pin: {"net": p["net"], "alternatives": p.get("alternatives", [])}
                            for pin, p in c["pins"].items()}} for c in obs["components"]],
                "ports": {name: {"net": p["net"], "alternatives": p.get("alternatives", [])}
                          for name, p in obs.get("ports", {}).items()},
                "board_topology_id": obs.get("source", {}).get("board_topology_id")}
    physical_key = stable_id("physical_", physical)
    if obs.get('source',{}).get('image_sha256') is not None:
        physical['image_sha256']=obs['source']['image_sha256']
        physical['media_binding']=obs['source'].get('media_binding')
        physical_key=stable_id('physical_',physical)
    if obs["revision"] == previous_revision and state.get("physical_key", physical_key) != physical_key:
        raise ValueError("physical observations changed without incrementing revision")
    result = diagnose_input(request, simulator)
    fingerprint = stable_id("input_", request)
    updated = deepcopy(state)
    updated.update(reference_key=reference_key, source_key=source_key, revision=obs["revision"], physical_key=physical_key)
    snapshots = updated["snapshots"]
    repeated = bool(snapshots and snapshots[-1]["input_id"] == fingerprint)
    if not repeated or snapshots[-1]["result"] != result:
        if len(snapshots) == 100:
            raise ValueError("session history full")
        snapshots.append({"input_id": fingerprint, "result": deepcopy(result)})
    return {"result": result, "state": updated, "unchanged_input": repeated}
