"""Exercise the real backend extraction method with local ML1, no HTTP or product data."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-ref', default='origin/backend/android-connection-test')
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new output file')
    # Execute only the selected actual extract method; full backend startup would
    # import credentials, persistence and product-memory integrations unnecessarily.
    source = subprocess.run(['git','show',f'{args.backend_ref}:backend/integrations.py'],
                            check=True,capture_output=True,text=True).stdout
    tree = ast.parse(source)
    owner = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Integrations')
    method = next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='extract')
    from labvision.upload import extract_upload
    namespace = {'extract_upload': extract_upload}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-backend-extract>','exec'),namespace)
    os.environ['LABVISION_ENDPOINT_WEIGHTS'] = str(args.weights.resolve())
    board = json.loads(args.board.read_text(encoding='utf-8-sig'))
    result = namespace['extract'](SimpleNamespace(settings=SimpleNamespace(vision_enabled=False)),
        args.image.read_bytes(), {'board':board,'reported_parts':['7400','led']})
    assert result['endpoint_detection']['status'] == 'unreviewed_region_proposals'
    assert result['netlist'] is None
    assert result['candidate']['reviewed_revision'] is None
    assert result['candidate']['wires'] == []
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed', 'backend_ref':args.backend_ref,
        'proposals':len(result['endpoint_detection']['videos'][0]['frames'][0]['proposals']),
        'mode':result['mode'], 'scope':'actual backend extract method only; no HTTP/deployment test',
        'output':str(args.out)}))


if __name__ == '__main__':
    main()
