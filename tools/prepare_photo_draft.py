"""Import image-specific assistant observations into a separate review session."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labvision.annotation import candidate_from_session, verify_session
from labvision.assistance import prepare_draft
from labvision.core import endpoints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        parser.error("Use a new/empty output folder to preserve earlier work")
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8-sig"))
    source = verify_session(read(args.session), args.image)
    observations = read(args.observations)
    draft = prepare_draft(source, observations)
    candidate = candidate_from_session(draft)
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (("draft.annotations.json", draft), ("draft.board.json", draft["board"]),
                        ("draft.candidate.json", candidate)):
        (out/name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    points = list(endpoints(candidate))
    summary = {"mapped_endpoints": sum(p["hole"] is not None for _, p, _ in points),
               "unresolved_endpoints": [name for name, p, _ in points if p["hole"] is None],
               "unverified_rail_holes": draft["board"].get("unverified_rail_holes", []),
               "status": "unreviewed assistant draft; not training ground truth",
               "source_session": str(Path(args.session).resolve()),
               "image_sha256": draft["image_sha256"]}
    (out/"summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = ["# Assisted photo draft", "", summary["status"], "",
              f"Mapped endpoints: {summary['mapped_endpoints']}. "
              f"Unresolved endpoints: {len(summary['unresolved_endpoints'])}.", "",
              "The 14 chip positions are generated from the visible DIP placement and a notch-at-bottom "
              "orientation hypothesis. Occluded pin positions are not visible training labels. "
              "Wire pairing is a visual proposal; verify crossings. LED polarity and outer-rail "
              "continuity remain unresolved. External clip ends are outside the hole-based schema.", "",
              "| Endpoint | Proposed hole | Evidence / remaining question |", "|---|---|---|"]
    for name, p, _ in points:
        report.append(f"| {name} | {p['hole'] or '?'} | {p['reason']} |")
    (out/"REVIEW.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
