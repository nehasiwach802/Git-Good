"""Offline check against actual ML3 git snapshots, without changing branches."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
PROBE='''import json,sys
sys.path.insert(0,sys.argv[1]);sys.path.insert(1,sys.argv[2])
from mentor import DiagnosticResult,EvidenceItem,explain_diagnostic
from reasoning.api import diagnose_input
from reasoning.ml3_bridge import explain
request=json.loads(sys.stdin.read())
diagnostic=diagnose_input(request)
before=json.dumps(diagnostic,sort_keys=True)
result=explain(diagnostic,'synthetic-contract-check',diagnostic_type=DiagnosticResult,
    evidence_type=EvidenceItem,explain_callback=explain_diagnostic)
assert json.dumps(diagnostic,sort_keys=True)==before
assert result['cause_probabilities'] is None
assert result['next_action']==diagnostic['next_check']['reason']
print(json.dumps({'status':result['status'],'model_status':result.get('model_status'),
    'wording_source':result.get('wording_source'),'diagnostic_unchanged':True,
    'probabilities_fabricated':False}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refs',nargs='+',default=['origin/Manit','backend/android-connection-test'])
    args=parser.parse_args()
    request=(ROOT/'examples/generalized/ml1-7400.json').read_text()
    reports=[]
    for ref in args.refs:
        with TemporaryDirectory(prefix='ml2-contract-') as directory:
            names=subprocess.check_output(['git','ls-tree','--name-only',ref],cwd=ROOT,text=True).splitlines()
            for name in names:
                if name.endswith('.py'):
                    Path(directory,name).write_bytes(subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT))
            result=subprocess.run([sys.executable,'-c',PROBE,directory,str(ROOT)],cwd=ROOT,
                input=request,text=True,capture_output=True,timeout=30)
            if result.returncode:raise RuntimeError('Contract probe failed for '+ref)
            reports.append({'ref':ref,**json.loads(result.stdout)})
    target=ROOT/'outputs/contracts/team-alignment.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(reports,indent=2)+'\n')
    for report in reports:print(json.dumps(report))
    print('Saved outputs/contracts/team-alignment.json')


if __name__=='__main__':main()
