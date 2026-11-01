"""Generate synthetic labelled fixtures; these are NOT labels for the user's photo."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from labvision.core import endpoint, make_board


def build_candidate():
    pin_holes = {str(pin): f"E{pin + 9}" for pin in range(1, 8)}
    pin_holes.update({str(pin): f"F{24 - pin}" for pin in range(8, 15)})
    wire_pairs = [("A10", "A11"), ("A13", "A16"), ("A14", "B16"),
                  ("J15", "C16"), ("J14", "D16"), ("J12", "B13"), ("J11", "B14")]
    return {
        "schema_version": "0.1", "candidate_id": "synthetic-7400-not-001", "revision": 1,
        "board_profile_id": "terminal-strips-30-no-rails", "board_confirmed": False,
        "reviewed_revision": None,
        "components": [{"id": "U1", "part": "7400", "identity_confirmed": False,
                        "pins": {pin: endpoint(hole, confidence="likely")
                                 for pin, hole in pin_holes.items()}}],
        "wires": [{"id": f"W{i}", "a": endpoint(a, confidence="likely"),
                   "b": endpoint(b, confidence="likely")}
                  for i, (a, b) in enumerate(wire_pairs, 1)],
        "ports": [{"id": name, "role": role, "endpoint": endpoint(hole, confidence="likely")}
                  for name, role, hole in [("A", "input", "B10"), ("Y", "output", "B12"),
                                           ("VCC", "vcc", "J10"), ("GND", "gnd", "C13")]],
        "issues": ["Synthetic software fixture, not extracted from a real photograph.",
                   "14-pin DIP, notch toward row 10. Rails deliberately excluded.",
                   "No LED/load included; ideal Boolean test fixture only."],
    }


if __name__ == "__main__":
    directory = ROOT / "examples"
    directory.mkdir(exist_ok=True)
    for name, value in (("board-30.json", make_board(30)),
                        ("7400-not.candidate.json", build_candidate())):
        (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print("Generated synthetic board and unreviewed 7400 candidate in examples/")
