"""Run a local wire-tip development check against one user-reviewed photo."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.annotation import verify_session
from labvision.core import require
from labvision.localvision import propose_red_wire_tips


def compare_holes(proposals, reference):
    predicted = Counter(p["hole"] for p in proposals if p.get("hole") is not None)
    expected = Counter(reference)
    matches = sum((predicted & expected).values())
    return {"matched": matches, "predicted": sum(predicted.values()), "reference": sum(expected.values()),
            "precision": matches/sum(predicted.values()) if predicted else 0,
            "recall": matches/sum(expected.values()) if expected else 0,
            "missed_holes": list((expected-predicted).elements()),
            "extra_holes": list((predicted-expected).elements())}


def main():
    from PIL import Image, ImageDraw
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--session", required=True)
    parser.add_argument("--reviewed-netlist", required=True)
    parser.add_argument("--crop", nargs=4, type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    require(not out.exists() or not any(out.iterdir()), "Use a new/empty output directory")
    session = verify_session(json.loads(Path(args.session).read_text(encoding="utf-8-sig")), args.image)
    netlist = json.loads(Path(args.reviewed_netlist).read_text(encoding="utf-8-sig"))
    require(netlist["status"] == "reviewed_connectivity", "reviewed reference required")
    require(netlist["candidate_id"] == session["candidate"]["candidate_id"]
            and netlist["revision"] == session["candidate"]["revision"], "session/netlist revisions differ")
    with Image.open(args.image) as opened:
        image = opened.convert("RGB")
    # Predictor receives pixels, board geometry and calibration only. Reference
    # endpoint labels are collected AFTER prediction and never passed to it.
    result = propose_red_wire_tips(image, session["board"], session["calibration"], args.crop)
    reference = []
    for wire in session["candidate"]["wires"]:
        for side in ("a", "b"):
            p = netlist["provenance"][wire["id"] + "." + side]
            require(p["confirmed"], "unconfirmed reference endpoint")
            if p.get("visible") is True and re.fullmatch(r"[A-J][1-9][0-9]*", p.get("hole") or ""):
                reference.append(p["hole"])
    metrics = compare_holes(result["proposals"], reference)
    metadata = {"image_sha256": hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),
                "assembly_id": session["assembly_id"], "evaluation_scope": "single-photo development check",
                "not_held_out": True, "reference_labels_passed_to_predictor": False,
                "rails_excluded_to_avoid_sparse_label_leakage": True, "metrics": metrics}
    out.mkdir(parents=True, exist_ok=True)
    result.pop("mask").save(out/"mask.png")
    result.pop("skeleton").save(out/"skeleton.png")
    (out/"proposals.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out/"evaluation.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    draw = ImageDraw.Draw(image)
    for p in result["proposals"]:
        xy = p["insertion_xy"] or p["tip_xy"]
        x, y = xy
        draw.ellipse((x-5, y-5, x+5, y+5), outline="#00ffff", width=2)
        draw.text((x+7, y-8), p["id"]+":"+(p["hole"] or "?"), fill="#00ffff", stroke_width=1, stroke_fill="black")
    image.save(out/"overlay.png")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
