"""Run synthetic JSON through the real application; never invokes Gemini."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reasoning.api import diagnose_input

CASES={"vision-7400":"review_learning_objective",
       "vision-7400-wrong-wire":"review_wiring",
       "vision-7400-unreviewed":"confirm_connections",
       "vision-rc":"explain_prediction"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'outputs'/'demo')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    for name,expected in CASES.items():
        request=json.loads((ROOT/'examples'/f'{name}.json').read_text(encoding='utf-8'))
        result=diagnose_input(request)
        if result['next_check']['kind']!=expected:
            raise RuntimeError(f'{name}: unexpected next check {result["next_check"]["kind"]}')
        if name=='vision-rc' and any(p['student']['status']!='ok' for p in result['predictions']):
            raise RuntimeError('Real ngspice prediction unavailable; configure NGSPICE_EXECUTABLE')
        (args.out/f'{name}.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        summary={'case':name,'status':result['status'],'next_check':result['next_check']['kind']}
        if result.get('logic_check'):
            summary['topology_matches']=result['logic_check']['topology_matches']
            summary['truth_table']=result['logic_check']['truth_table']
        if name=='vision-rc':
            summary['predicted_v']=result['predictions'][0]['student']['value']
            summary['concept_support']=result['hypotheses']['concept']['support']
        print(json.dumps(summary))
    try:
        display=str(args.out.relative_to(ROOT))
    except ValueError:
        display=json.dumps(str(args.out))
    print('Full responses saved to '+display)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
