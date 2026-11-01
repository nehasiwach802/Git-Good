"""Run with python -m labvision; core commands are dependency-free, image tools use Pillow."""

import argparse
import json
from pathlib import Path
import sys

from .core import (CandidateError, compile_netlist, confirm, correct, make_board,
                   pending, validate)
from .digital import check_not
from .vision import extract, prompt
from .review import review_markdown


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(value, path=None):
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main(argv=None):
    parser = argparse.ArgumentParser(description="ML1 breadboard-to-reviewed-netlist prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    board_cmd = sub.add_parser("board", help="generate a terminal-strip-only profile")
    board_cmd.add_argument("--rows", type=int, default=63)
    board_cmd.add_argument("--out", required=True)
    annotation_cmd = sub.add_parser("annotate", help="open local calibration/endpoint annotation window")
    annotation_cmd.add_argument("image")
    annotation_cmd.add_argument("--board", required=True)
    annotation_cmd.add_argument("--assembly-id", default="assembly-001")
    annotation_cmd.add_argument("--candidate", help="optional candidate to annotate; image binding is checked")
    annotation_cmd.add_argument("--session", help="resume saved annotations for this image")
    synth_cmd = sub.add_parser("synthetic", help="generate stylized PNG scenes and exact labels")
    synth_cmd.add_argument("--out", required=True)
    synth_cmd.add_argument("--count", type=int, default=200)
    synth_cmd.add_argument("--seed", type=int, default=42)
    synth_cmd.add_argument("--variants", type=int, default=2)
    calibration_cmd = sub.add_parser("calibrate", help="fit a homography from anchors/checks JSON")
    calibration_cmd.add_argument("anchors")
    calibration_cmd.add_argument("--board", required=True)
    calibration_cmd.add_argument("--out", required=True)
    for name in ("inspect", "report", "correct", "confirm", "export", "check-not", "extract", "prompt"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--board", required=True)
        cmd.add_argument("--out")
        if name not in ("extract", "prompt"):
            cmd.add_argument("candidate")
        if name in ("correct", "confirm"):
            cmd.add_argument("--expected-revision", required=True, type=int)
            # Require a new output file, so the source remains reviewable.
        if name == "correct":
            cmd.add_argument("--target", required=True, help="U1.1, W1.a or input port ID")
            cmd.add_argument("--hole", required=True)
        if name == "confirm":
            cmd.add_argument("--reviewed", action="store_true", required=True,
                             help="I reviewed board topology, all parts/pins/wires/ports and omissions")
        if name == "check-not":
            cmd.add_argument("--component", default="U1")
            cmd.add_argument("--gate", type=int, default=1)
        if name == "extract":
            cmd.add_argument("image")
            cmd.add_argument("--model", help="otherwise read GEMINI_MODEL")
            cmd.add_argument("--timeout", type=float, default=45,
                             help="provider timeout in seconds (maximum 300)")
            cmd.add_argument("--raw-response", help="optional local provider-response JSON for debugging")
            cmd.add_argument("--thinking-level", choices=("low", "medium", "high"),
                             help="optional thinking effort, only for models supporting this setting")
            cmd.add_argument("--known-part", action="append",
                             help="student-reported part identity; repeat for more parts (no wiring hints)")
    args = parser.parse_args(argv)
    try:
        if args.command == "board":
            result = make_board(args.rows)
        elif args.command == "annotate":
            from .annotator import launch
            launch(args.image, read(args.board), args.assembly_id,
                   read(args.candidate) if args.candidate else None, args.session)
            return 0
        elif args.command == "synthetic":
            from .synthetic import generate
            result = generate(args.out, args.count, args.seed, args.variants)
            write(result)
            return 0
        elif args.command == "calibrate":
            from .geometry import calibrate
            anchors = read(args.anchors)
            result = calibrate(read(args.board), anchors["anchors"], anchors.get("checks", []))
        else:
            board = read(args.board)
            if args.command == "extract":
                result = extract(args.image, board, args.model, args.timeout, args.raw_response,
                                 args.thinking_level, args.known_part)
            elif args.command == "prompt":
                result = {"prompt": prompt(board)}
            else:
                candidate = read(args.candidate)
                validate(candidate, board)
                if args.command == "inspect":
                    result = {"candidate_id": candidate["candidate_id"],
                              "revision": candidate["revision"],
                              "pending": pending(candidate, board), "issues": candidate["issues"]}
                elif args.command == "report":
                    report = review_markdown(candidate, board)
                    if args.out:
                        target = Path(args.out)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(report, encoding="utf-8")
                    else:
                        print(report)
                    return 0
                elif args.command == "correct":
                    result = correct(candidate, board, args.target, args.hole, args.expected_revision)
                elif args.command == "confirm":
                    result = confirm(candidate, board, args.expected_revision)
                elif args.command == "export":
                    result = compile_netlist(candidate, board)
                else:
                    result = check_not(compile_netlist(candidate, board), args.component, args.gate)
        if getattr(args, "out", None) and args.command in ("correct", "confirm"):
            if Path(args.out).resolve() == Path(args.candidate).resolve():
                raise CandidateError("Use a different output path to preserve the source revision")
        write(result, args.out)
        if args.command == "check-not" and not result["topology_matches"]:
            return 1
        return 0
    except (CandidateError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
