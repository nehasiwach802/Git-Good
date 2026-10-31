"""Image-bound annotation sessions; candidate schema stays at version 0.1."""

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import uuid

from .core import PART_PINS, CandidateError, endpoint, endpoints, require, validate
from .geometry import board_fingerprint, calibrate, calibration_quality, hole_positions, point, project, snap


def new_session(image_path, image_size, board, assembly_id, candidate=None):
    width, height = image_size
    require(type(width) is int and type(height) is int and width > 0 and height > 0,
            "image dimensions must be positive integers")
    require(isinstance(assembly_id, str) and assembly_id.strip(), "assembly_id required for dataset splitting")
    candidate = deepcopy(candidate) if candidate is not None else {
        "schema_version": "0.1", "candidate_id": "annotated-" + uuid.uuid4().hex,
        "revision": 1, "board_profile_id": board["id"], "board_confirmed": False,
        "reviewed_revision": None, "components": [], "wires": [], "ports": [],
        "issues": ["Manual pixel annotations; full physical circuit review is required."],
    }
    image_hash = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    require(candidate["board_profile_id"] == board["id"], "candidate board profile mismatch")
    require(candidate.get("image_sha256") in (None, image_hash), "candidate belongs to another image")
    for _, p, _ in endpoints(candidate):
        p["confirmed"] = False
        if candidate.get("image_sha256") is None:
            p.update(hole=None, alternatives=[], confidence="unknown", image_xy=None,
                     reason="Import has no image binding; annotate endpoint on this image")
    for component in candidate["components"]:
        component["identity_confirmed"] = False
    candidate.update(board_confirmed=False, reviewed_revision=None)
    return {"annotation_version": "0.1", "image_sha256": image_hash,
            "image_name": Path(image_path).name, "image_size": [width, height],
            "assembly_id": assembly_id.strip(), "image_type": "real", "board": deepcopy(board),
            "calibration": None, "candidate": candidate}


def invalidate(session):
    candidate = session["candidate"]
    candidate["revision"] += 1
    candidate["reviewed_revision"] = None
    candidate["board_confirmed"] = False


def add_outer_hole(session, identifier, xy):
    """Record a measured outer hole without inventing its rail connectivity."""
    import re
    require(re.fullmatch(r"R[1-9][0-9]*", identifier) is not None,
            "outer hole IDs must be R1, R2, ...")
    calibration = session.get("calibration")
    require(calibration is not None, "calibrate the central grid first")
    board = deepcopy(session["board"])
    positions = hole_positions(board)
    require(identifier not in positions, "hole ID already exists")
    location = project(calibration["image_to_board"], point(xy))
    require(min(math.dist(location, p) for p in positions.values()) > 0.5,
            "too close to an existing hole; select that hole instead")
    positions[identifier] = location
    board["hole_positions"] = positions
    board["groups"].append([identifier])
    board.setdefault("unverified_rail_holes", []).append(identifier)
    hole_positions(board)
    session["board"] = board
    calibration["board_fingerprint"] = board_fingerprint(board)
    invalidate(session)


def set_calibration(session, anchors, checks=None):
    # Commit only after validation; old clicked endpoints belong to the old mapping.
    result = calibrate(session["board"], anchors, checks)
    for _, p, _ in endpoints(session["candidate"]):
        if p.get("image_xy") is not None:
            p.update(hole=None, alternatives=[], confidence="unknown", confirmed=False,
                     reason="Calibration changed; annotate this endpoint again")
        else:
            p["confirmed"] = False
    session["calibration"] = result
    invalidate(session)


def add_component(session, part, identifier, value_si=None):
    require(part in PART_PINS, "unsupported part")
    item = {"id": identifier, "part": part, "identity_confirmed": False,
            "pins": {pin: endpoint() for pin in sorted(PART_PINS[part], key=lambda s: (len(s), s))}}
    if part in ("resistor", "capacitor"):
        require(value_si is None or (type(value_si) in (int, float) and math.isfinite(value_si) and value_si > 0),
                "component value must be a positive SI number")
        item.update(value_si=value_si, value_confirmed=False)
    _add(session, "components", item)


def add_wire(session, identifier):
    _add(session, "wires", {"id": identifier, "a": endpoint(), "b": endpoint()})


def add_port(session, identifier, role):
    require(role in ("input", "output", "vcc", "gnd"), "invalid port role")
    _add(session, "ports", {"id": identifier, "role": role, "endpoint": endpoint()})


def _add(session, field, item):
    import re
    require(isinstance(item["id"], str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", item["id"]), "invalid ID")
    require(all(item["id"] != obj["id"] for field_name in ("components", "wires", "ports")
                for obj in session["candidate"][field_name]), "duplicate ID")
    session["candidate"][field].append(item)
    invalidate(session)


def remove_item(session, identifier):
    for field in ("components", "wires", "ports"):
        for index, obj in enumerate(session["candidate"][field]):
            if obj["id"] == identifier:
                del session["candidate"][field][index]
                invalidate(session)
                return
    raise CandidateError("item ID not found")


def annotate(session, target, xy=None, visible=True):
    matches = [p for name, p, _ in endpoints(session["candidate"]) if name == target]
    require(len(matches) == 1, "select an existing endpoint")
    if visible:
        require(session["calibration"] is not None, "calibrate the image first")
        x, y = point(xy)
        width, height = session["image_size"]
        require(0 <= x < width and 0 <= y < height, "point is outside image")
        updated = snap(session["calibration"], session["board"], [x, y])
        if updated["hole"] is not None:
            occupied = {p["hole"] for name, p, physical in endpoints(session["candidate"])
                        if physical and name != target and p["hole"] is not None}
            target_physical = next(physical for name, _, physical in endpoints(session["candidate"]) if name == target)
            require(not target_physical or updated["hole"] not in occupied,
                    "hole already occupied; ports can share holes but inserted leads cannot")
    else:
        updated = dict(endpoint(), visible=False, image_xy=None,
                       reason="Insertion point occluded or not established; do not infer it")
    matches[0].clear()
    matches[0].update(updated)
    invalidate(session)
    return updated


def verify_session(session, image_path):
    require(session.get("annotation_version") == "0.1", "unsupported annotation version")
    actual = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    require(session.get("image_sha256") == actual, "session belongs to a different image")
    if session.get("calibration"):
        require(session["calibration"]["board_fingerprint"] == board_fingerprint(session["board"]),
                "session board geometry changed")
    return session


def candidate_from_session(session):
    require(session.get("calibration") is not None, "calibration required")
    require(calibration_quality(session["calibration"], session["board"])["validated"],
            "validate calibration using two additional distinct hole centers first")
    candidate = deepcopy(session["candidate"])
    candidate["image_sha256"] = session["image_sha256"]
    candidate["annotation_assembly_id"] = session["assembly_id"]
    candidate["image_type"] = session["image_type"]
    validate(candidate, session["board"])
    return candidate


def training_record(session, reviewed=False):
    require(reviewed is True, "explicit annotation review is required")
    require(session.get("calibration") is not None, "calibration required")
    quality = calibration_quality(session["calibration"], session["board"])
    require(quality["validated"], "validate calibration using two separate known holes first")

    def label(p):
        # Imported model-only hole guesses are not manually labelled image evidence.
        observed = (p.get("source") == "manual" and p.get("image_xy") is not None
                    and p.get("visible", True) is True)
        hidden = p.get("visible") is False
        return {"xy": p.get("image_xy") if observed else None,
                "hole": p["hole"] if observed else None,
                "observable_hole": p["hole"] if observed else None,
                "visible": True if observed else False if hidden else None,
                "label_status": "annotated" if observed else "occluded" if hidden else "unlabelled"}

    return {"label_version": "0.1", "image_type": session["image_type"],
            "image_name": session["image_name"], "image_sha256": session["image_sha256"],
            "image_size": session["image_size"], "assembly_id": session["assembly_id"],
            "label_reviewed": True, "board_profile_id": session["board"]["id"],
            "board_to_image": session["calibration"]["board_to_image"],
            "calibration_quality": quality,
            "hole_centers": {h: project(session["calibration"]["board_to_image"], p)
                             for h, p in hole_positions(session["board"]).items()},
            "components": [{"id": c["id"], "part": c["part"], "mask_id": None,
                            "pins": {pin: label(p) for pin, p in c["pins"].items()}}
                           for c in session["candidate"]["components"]],
            "wires": [{"id": w["id"], "mask_id": None, "a": label(w["a"]),
                       "b": label(w["b"]), "path_xy": None,
                       "pairing_reviewed": w.get("pairing_reviewed", True)}
                      for w in session["candidate"]["wires"]],
            "electrical_groups": None,
            "limitations": ["Real annotations can be partial. visible=null means unlabelled, not occluded.",
                            "Projected grid centers are calibration estimates, not measured hidden hole centers.",
                            "No manually annotated wire paths/masks are available in this tool version."]}
