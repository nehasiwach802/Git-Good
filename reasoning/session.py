"""Optional backend helper for replayable diagnostic history, without storage.

Callers store the returned state in their own authorized session store. Previous
findings are historical only; current hypotheses are recomputed from current
inputs so a corrected circuit does not inherit stale fault support.
"""
from copy import deepcopy
from .engine import diagnose
from .checks import stable_id
from .spice import simulate


def advance_session(request, state=None, simulator=simulate):
    if state is None:
        state = {"version": 1, "snapshots": []}
    if (not isinstance(state, dict) or state.get("version") != 1
            or not isinstance(state.get("snapshots"), list)
            or len(state["snapshots"]) > 100
            or not all(isinstance(s, dict) and isinstance(s.get("input_id"), str)
                       and isinstance(s.get("result"), dict) for s in state["snapshots"])):
        raise ValueError("invalid session state; maximum 100 snapshots")
    result = diagnose(request, simulator)
    experiment_key = stable_id("experiment_", request["experiment"])
    if state.get("experiment_key", experiment_key) != experiment_key:
        raise ValueError("start a new session when the reference experiment changes")
    previous_source = state.get("source_context")
    current_source = request.get("source_context")
    if previous_source is not None and (
            not isinstance(previous_source, dict)
            or not isinstance(previous_source.get("board_id"), str)
            or any(isinstance(previous_source.get(k), bool)
                   or not isinstance(previous_source.get(k), int)
                   or previous_source[k] < 0 for k in ("candidate_revision", "reviewed_revision"))):
        raise ValueError("invalid session source context")
    if previous_source:
        if not current_source or previous_source["board_id"] != current_source["board_id"]:
            raise ValueError("start a new session when source board changes; source context cannot be dropped")
        if current_source["candidate_revision"] < previous_source["candidate_revision"]:
            raise ValueError("stale candidate revision; session already contains a newer circuit")
    fingerprint = stable_id("input_", request)
    updated = deepcopy(state)
    updated["experiment_key"] = experiment_key
    if current_source:
        updated["source_context"] = deepcopy(current_source)
    snapshots = updated["snapshots"]
    repeated = bool(snapshots and snapshots[-1].get("input_id") == fingerprint)
    if not repeated or snapshots[-1]["result"] != result:
        if len(snapshots) == 100:
            raise ValueError("session history full; archive before continuing")
        snapshots.append({"input_id": fingerprint, "result": deepcopy(result)})
    return {"result": result, "state": updated, "unchanged_input": repeated}
