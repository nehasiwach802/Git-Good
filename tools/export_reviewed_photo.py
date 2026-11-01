"""Package one image and partial labels using an exact matching reviewed netlist."""

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.annotation import verify_session
from labvision.core import require
from labvision.dataset import labels_from_reviewed_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--session", required=True)
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    require(not out.exists() or not any(out.iterdir()), "Use a new/empty output directory")
    session = verify_session(json.loads(Path(args.session).read_text(encoding="utf-8-sig")), args.image)
    netlist = json.loads(Path(args.netlist).read_text(encoding="utf-8-sig"))
    labels = labels_from_reviewed_export(session, netlist)
    (out/"images").mkdir(parents=True, exist_ok=True)
    (out/"labels").mkdir()
    filename = "real-001" + Path(args.image).suffix.lower()
    shutil.copyfile(args.image, out/"images"/filename)
    (out/"labels/real-001.json").write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    (out/"reviewed.netlist.json").write_text(json.dumps(netlist, indent=2) + "\n", encoding="utf-8")
    points = [p for c in labels["components"] for p in c["pins"].values()]
    points += [w[side] for w in labels["wires"] for side in ("a", "b")]
    manifest = {"scene_id": "real-001", "image_type": "real", "image": "images/"+filename,
                "labels": "labels/real-001.json", "image_sha256": session["image_sha256"],
                "assembly_id": session["assembly_id"], "split": "unassigned",
                "reviewed_revision": netlist["revision"],
                "visible_labelled_endpoints": sum(p["label_status"] == "annotated" for p in points),
                "unlabelled_or_hidden_endpoints": sum(p["label_status"] != "annotated" for p in points),
                "notes": "One reviewed build; partial visible labels; no independent evaluation split or correctness label"}
    (out/"manifest.jsonl").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
