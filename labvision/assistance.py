"""Image-bound, unreviewed photo proposals and explicit object-level review.

These helpers import observations; they are not a trained image detector.
"""

from copy import deepcopy

from .annotation import add_component, add_outer_hole, add_wire, invalidate
from .core import endpoints, require, validate, resolved
from .geometry import board_fingerprint, hole_positions, point, project, snap


def prepare_draft(session, observations):
    require(observations["image_sha256"] == session["image_sha256"],
            "observations belong to a different image")
    require(observations["calibration_fingerprint"] == board_fingerprint(session["board"]),
            "observations were prepared for different board geometry")
    result = deepcopy(session)
    for hole in observations.get("outer_holes", []):
        add_outer_hole(result, hole["id"], hole["xy"])
    if observations.get("outer_holes"):
        result["board"]["id"] += "-draft-" + session["image_sha256"][:8]
        result["candidate"]["board_profile_id"] = result["board"]["id"]
        result["calibration"]["board_fingerprint"] = board_fingerprint(result["board"])
    for item in observations.get("objects", []):
        existing = [o for field in ("components", "wires", "ports")
                    for o in result["candidate"][field] if o["id"] == item["id"]]
        if not existing:
            if item["kind"] == "wire":
                add_wire(result, item["id"])
            else:
                add_component(result, item["part"], item["id"])
        if item["kind"] == "wire":
            wire = next(w for w in result["candidate"]["wires"] if w["id"] == item["id"])
            wire.setdefault("pairing_reviewed", False)
            wire["draft_description"] = item.get("description", "")
    lookup = {name: p for name, p, _ in endpoints(result["candidate"])}
    for observation in observations["endpoints"]:
        target = observation["target"]
        require(target in lookup, "unknown draft endpoint: " + target)
        old = lookup[target]
        # Preserve real edits, including a user's explicit hidden endpoint.
        if old.get("source") == "manual" and (old.get("image_xy") is not None
                or resolved(old) or old.get("visible") is False):
            continue
        xy = observation.get("xy")
        if observation.get("projected_hole"):
            xy = project(result["calibration"]["board_to_image"],
                         hole_positions(result["board"])[observation["projected_hole"]])
        if xy is not None:
            x, y = point(xy)
            width, height = result["image_size"]
            require(0 <= x < width and 0 <= y < height, "draft point outside image")
            proposed = snap(result["calibration"], result["board"], xy)
        else:
            proposed = dict(old, hole=None, image_xy=None, alternatives=[])
        if observation.get("unresolved"):
            proposed["hole"] = None
            proposed["alternatives"] = observation.get("alternatives", [])
        proposed.update(source="vision", confirmed=False,
                        confidence="likely" if proposed["hole"] else "uncertain",
                        visible=observation.get("visible"),
                        reason=observation["reason"],
                        proposal_origin="assistant-photo-review",
                        proposal_reviewed=False)
        old.clear()
        old.update(proposed)
    invalidate(result)
    result["candidate"]["issues"].append(
        "Assistant photo draft: positions, pairing, polarity and rail topology need review; not ground truth.")
    result["assistance"] = {"method": "assistant visual observations plus existing calibrated geometry",
                            "reviewed": False, "image_sha256": session["image_sha256"]}
    validate(result["candidate"], result["board"])
    return result


def accept_object_draft(session, identifier):
    """Explicit user review of mapped endpoints and, if complete, wire pairing."""
    candidate = session["candidate"]
    validate(candidate, session["board"])
    selected = [(name, p) for name, p, _ in endpoints(candidate)
                if name.split(".")[0] == identifier]
    accepted = [p for _, p in selected if p.get("source") == "vision"
                and resolved(p) and not p.get("alternatives")]
    require(accepted, "No mapped draft to accept; unresolved endpoints need a correction")
    for p in accepted:
        p.update(source="manual", proposal_reviewed=True, confirmed=False)
        p["reason"] = "User accepted assistant proposal: " + p["reason"]
    for wire in candidate["wires"]:
        if wire["id"] == identifier:
            wire["pairing_reviewed"] = all(resolved(p)
                and not p.get("alternatives") and p.get("source") == "manual"
                for p in (wire["a"], wire["b"]))
    invalidate(session)
    return len(accepted)
