"""Build an ML1-only handoff archive. No backend, Android replacement or secrets."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from labvision.config import gemini_settings
from labvision.core import require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--run-checks', action='store_true')
    parser.add_argument('--weights', type=Path, help='Include explicit trusted local endpoint checkpoint')
    args = parser.parse_args()
    target = Path(args.out)
    require(not target.exists(), 'Use a new archive path to preserve earlier releases')
    files = []
    for folder in ('labvision', 'tests', 'tools'):
        files.extend(p for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts)
    for folder in ('docs', 'reports'):
        files.extend((ROOT/folder).glob('*.md'))
    files.extend((ROOT/'examples').rglob('*.json'))
    files.extend((ROOT/'ckt breadboard').glob('*.jpeg'))
    files.extend(ROOT/name for name in ('LICENSE', 'AGENTS.md', 'context.md',
        'requirements-vision.txt', 'requirements-local-vision.txt', 'ML1_PLAN.md',
        'EXPERIMENT_RESOURCES.md', 'VISION_DATA_STRATEGY.md'))
    files.extend(ROOT.glob('requirements-*.txt'))
    names = [p.relative_to(ROOT).as_posix() for p in files]
    require(not any(name.startswith(('backend/', 'reasoning/', 'integrations/', '.env')) for name in names),
            'Release contains files outside ML1 scope')
    require(not any(p.name.startswith('api') or p.name == 'server.py' for p in files if p.parent.name == 'labvision'),
            'A replacement API must not be part of this ML1 release')
    key = gemini_settings()['GEMINI_API_KEY']
    for path in files:
        require(not key or key.encode() not in path.read_bytes(),
                'A configured credential was found in '+path.relative_to(ROOT).as_posix())
    checks = None
    if args.run_checks:
        run = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                             cwd=ROOT, capture_output=True, text=True)
        require(run.returncode == 0, 'ML1 checks failed; run the test suite before releasing')
        checks = run.stdout + run.stderr
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip())
    manifest = {'scope': 'ML1 library, reviewed observations and tests only',
                'source_commit': commit, 'working_tree_changes_included': dirty,
                'existing_backend': 'https://git-good-1.onrender.com/',
                'existing_upload_route': 'Use current teammate backend API contract; no routes supplied by this release',
                'http_server_included': False, 'android_client_included': False,
                'reference_or_reasoning_engine_included': False,
                'sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(set(files))}}
    if args.weights:
        require(args.weights.is_file(), 'Weights file missing')
        manifest['endpoint_checkpoint'] = {'file': 'models/endpoints.pt',
            'sha256': hashlib.sha256(args.weights.read_bytes()).hexdigest(),
            'target': 'wire_end_region', 'real_accuracy_established': False}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr('ML1_RELEASE.md', '# ML1 handoff\n\nStart with docs/VIDEO_PROCESSOR_HANDOFF.md '
            'for video and docs/UPLOAD_DETECTOR_INTEGRATION.md for images. '
            'docs/TEAM_INTEGRATION.md includes historical deployment notes. '
            'Use the existing deployed backend and ML2 adapters. Automatic vision is experimental.\n')
        archive.writestr('release-manifest.json', json.dumps(manifest, indent=2)+'\n')
        if args.weights:
            archive.write(args.weights, 'models/endpoints.pt')
        if checks is not None:
            archive.writestr('verification.txt', checks)
    with zipfile.ZipFile(target) as archive:
        require(archive.testzip() is None, 'Release archive integrity failed')
    print(json.dumps({'archive': str(target), 'files': len(set(files)), 'credential_scan': 'passed',
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'checks_run': args.run_checks}))


if __name__ == '__main__':
    main()
