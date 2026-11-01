"""Export ML1 files for the team's existing backend and reasoning adapters."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.annotation import verify_session
from labvision.core import require
from labvision.dataset import reviewed_candidate_from_export
from labvision.handoff import reasoning_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--session", required=True)
    parser.add_argument("--netlist", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    require(not out.exists() or not any(out.iterdir()), "Use a new/empty handoff directory")
    session = verify_session(json.loads(Path(args.session).read_text(encoding="utf-8-sig")), args.image)
    netlist = json.loads(Path(args.netlist).read_text(encoding="utf-8-sig"))
    candidate = reviewed_candidate_from_export(session, netlist)
    spec = reasoning_input(candidate, session["board"])
    out.mkdir(parents=True, exist_ok=True)
    for name, value in [("candidate.json", candidate), ("board.json", session["board"]),
                        ("reviewed-netlist.json", netlist), ("reasoning-input.json", spec)]:
        (out/name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"revision": candidate["revision"], "adapter": spec["adapter"], "output": str(out),
                      "note": "Observation only; backend supplies independent approved reference and identity maps"}))


if __name__ == "__main__":
    main()
