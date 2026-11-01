"""Derive partial training labels from an existing matching human-reviewed export."""

from copy import deepcopy

from .annotation import candidate_from_session, training_record
from .core import compile_netlist, confirm, endpoints, require


def reviewed_candidate_from_export(session, netlist):
    require(netlist.get("status") == "reviewed_connectivity", "human-reviewed netlist required")
    candidate = candidate_from_session(session)
    require(netlist.get("candidate_id") == candidate["candidate_id"]
            and netlist.get("revision") == candidate["revision"],
            "reviewed netlist belongs to another candidate or revision")
    # Existing reviewed export is the evidence of acknowledgement. A changed
    # hole, pixel, visibility, pairing or topology cannot inherit old review.
    reviewed = confirm(candidate, session["board"], candidate["revision"])
    require(compile_netlist(reviewed, session["board"]) == netlist,
            "saved session does not reproduce the reviewed export exactly")
    return reviewed


def labels_from_reviewed_export(session, netlist):
    reviewed = reviewed_candidate_from_export(session, netlist)
    accepted = deepcopy(session)
    accepted["candidate"] = reviewed
    original_sources = {}
    for name, p, _ in endpoints(accepted["candidate"]):
        original_sources[name] = p.get("source")
        p["source"] = "manual"
        p["proposal_reviewed"] = True
    for wire in accepted["candidate"]["wires"]:
        wire["pairing_reviewed"] = True
    record = training_record(accepted, reviewed=True)
    record["review_evidence"] = {"candidate_id": netlist["candidate_id"],
                                 "revision": netlist["revision"],
                                 "status": netlist["status"],
                                 "original_endpoint_sources": original_sources}
    record["limitations"].append(
        "Human-reviewed proposals are accepted annotations, not independent detector ground truth. "
        "Unknown-visibility pose projections remain unlabelled. Circuit correctness is not established.")
    return record
