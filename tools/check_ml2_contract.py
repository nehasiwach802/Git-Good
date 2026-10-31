"""Read-only compatibility check against the teammate-owned reasoning checkout."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ml2-root', required=True, help='Checkout containing the existing reasoning package')
    parser.add_argument('--input', required=True, help='ML1 reasoning-input.json to validate')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.ml2_root).resolve()))
    from reasoning.adapters import ADAPTERS
    from reasoning.observations import validate_observation
    from reasoning.registry import MODELS
    spec = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    result = ADAPTERS[spec['adapter']](spec['payload'])
    validate_observation(result)
    gaps = sorted({c['model'] for c in result['components'] if c['model'] not in MODELS})
    print(json.dumps({'ok': True, 'adapter': spec['adapter'], 'revision': result['revision'],
                      'components': len(result['components']), 'unsupported_models_preserved': gaps,
                      'scope': 'Existing ML2 parser/observation compatibility only, not simulation or hardware correctness'}))


if __name__ == '__main__':
    main()
