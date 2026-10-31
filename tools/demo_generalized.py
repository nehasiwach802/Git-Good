"""Show generalized comparisons and real predictions from synthetic inputs."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reasoning.api import diagnose_input


def main():
    output = ROOT / 'outputs' / 'generalized'
    output.mkdir(parents=True, exist_ok=True)
    for name in ('rc', 'rc-uncertain', 'rc-unknown', 'divider', 'ml1-7400'):
        request = json.loads((ROOT / 'examples' / 'generalized' / (name + '.json')).read_text())
        result = diagnose_input(request)
        (output / (name + '.json')).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        summary = {'case': name, 'status': result['status'],
                   'wiring': result['hypotheses']['wiring']['support'],
                   'next_check': result['next_check']['kind']}
        if result['predictions']:
            summary['prediction'] = result['predictions'][0]['student']
        print(json.dumps(summary))
    print('Full responses: outputs/generalized/')


if __name__ == '__main__':
    main()
