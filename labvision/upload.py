"""ML1 library entry point for the already-deployed multipart upload backend."""

import hashlib
import io
from pathlib import Path
import tempfile

from PIL import Image, UnidentifiedImageError

from .annotation import add_component, new_session
from .core import CandidateError, PART_PINS, endpoints, require, validate
from .geometry import hole_positions
from .vision import extract


def extract_upload(image_bytes, board, *, known_parts=None, try_vision=True,
                   timeout=20, extractor=None, detector=None):
    """Return unreviewed ML1 data for backend.app's existing ml1 response field.

    The backend owns experiment lookup, HTTP, sessions, identity and ML2/ML3.
    The supplied board is physical geometry, never reference circuit wiring.
    On provider failure, return a truthful manual-entry draft with null pins.
    """
    require(isinstance(image_bytes, bytes) and 0 < len(image_bytes) <= 5*1024*1024,
            "upload must contain JPEG/PNG bytes, at most 5 MiB")
    require(type(timeout) in (int, float) and 0 < timeout <= 30, "timeout must be greater than 0 and at most 30 seconds")
    require(type(try_vision) is bool, "try_vision must be a boolean")
    known_parts = list(known_parts or [])
    require(all(part in PART_PINS for part in known_parts), "unsupported reported part")
    hole_positions(board)
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            size, format_name = image.size, image.format
            require(format_name in ("JPEG", "PNG"), "only JPEG and PNG uploads are supported")
            require(size[0]*size[1] <= 20_000_000, "upload exceeds 20 megapixels")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise CandidateError("invalid uploaded image") from None
    mode, candidate, error_code = "manual", None, None
    detection = {'status': 'disabled'}
    with tempfile.TemporaryDirectory(prefix="labvision-upload-") as directory:
        path = Path(directory)/("capture.jpg" if format_name == "JPEG" else "capture.png")
        path.write_bytes(image_bytes)
        try:
            if detector is None:
                from .detection import configured_detector
                detector = configured_detector()
            if detector is not None:
                detection = detector(path, size, hashlib.sha256(image_bytes).hexdigest())
        except (CandidateError, ImportError, RuntimeError, OSError, ValueError):
            detection = {'status': 'unavailable', 'error_code': 'endpoint_detector_unavailable'}
        if try_vision:
            try:
                candidate = (extractor or extract)(path, board, timeout=timeout, known_parts=known_parts)
                candidate["image_sha256"] = hashlib.sha256(image_bytes).hexdigest()
                validate(candidate, board)
                mode = "gemini"
            except CandidateError:
                candidate, mode, error_code = None, "manual_fallback", "vision_unavailable"
        session = new_session(path, size, board, "backend-owned-assembly", candidate)
        if candidate is None:
            counts = {}
            for part in known_parts:
                prefix = {"7400": "U", "opamp": "U", "led": "D", "diode": "D", "resistor": "R", "capacitor": "C"}[part]
                counts[prefix] = counts.get(prefix, 0)+1
                add_component(session, part, prefix+str(counts[prefix]))
        candidate = session["candidate"]
        candidate["revision"] = 1
        candidate["image_sha256"] = session["image_sha256"]
        if mode == "gemini":
            for _, point, _ in endpoints(candidate):
                point["source"] = "vision"
        for component in candidate["components"]:
            if component["part"] in ("resistor", "capacitor"):
                component["value_confirmed"] = False
        for wire in candidate["wires"]:
            wire["pairing_reviewed"] = False
    points = list(endpoints(candidate))
    return {"mode": mode, "status": "needs_confirmation" if mode == "gemini" else "manual_entry_required",
            "endpoint_detection": detection,
            "candidate": candidate, "board": board, "netlist": None,
            "image": {"sha256": session["image_sha256"], "width": size[0], "height": size[1],
                      "content_type": "image/jpeg" if format_name == "JPEG" else "image/png",
                      "size_bytes": len(image_bytes), "coordinates": "native-file-pixels-no-exif-transform"},
            "unknown_endpoints": [name for name, p, _ in points if p["hole"] is None and not p.get("external_terminal")],
            "error_code": error_code,
            "message": "Review observed parts, connections and omissions before ML2 reasoning; reference wiring was not used."}
