"""Run a JSON fixture without Android, vision, memory or an HTTP server."""
import argparse
import json
import sys
from pathlib import Path
from .api import diagnose_input, validate_input
from .server import strict_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        request = strict_json(args.request.read_bytes())
        validate_input(request)
        result = {"valid": True} if args.validate_only else diagnose_input(request)
        output = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
