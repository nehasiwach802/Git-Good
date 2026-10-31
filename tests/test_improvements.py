import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from reasoning.circuit import diff, normalize
from reasoning.engine import diagnose
from reasoning.session import advance_session
from reasoning.validation import ValidationError
from reasoning.spice import simulate


def fixture():
    return json.loads(Path('examples/rc.json').read_text())


def prediction(circuit, probe):
    return {'status':'ok','value':.70710678}


class ImprovementsTests(unittest.TestCase):
    def test_bad_inputs_fail_even_before_confirmation(self):
        mutations = [
            lambda r: r['experiment']['probes'][0].update(frequency_hz=0),
            lambda r: r['experiment']['probes'][0].update(relative_tolerance=-1),
            lambda r: r.update(student_expectations={'unknown':1}),
            lambda r: r.update(equipment_evidence={'anomaly_follows_equipment':True}),
            lambda r: r.update(student_probe_nodes={'output':{'frequency_hz':5}}),
            lambda r: r.update(measurements={}),
            lambda r: r['student_circuit'].update(wires='bad'),
            lambda r: r['student_circuit']['components'][0].update(value=10**400),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                r = fixture()
                r.pop('safety_profile')
                mutate(r)
                with self.assertRaises(ValidationError) as error:
                    diagnose(r, prediction)
                self.assertTrue(error.exception.path.startswith('$'))

    def test_stable_evidence_and_check_metadata(self):
        a = diagnose(fixture(),prediction)
        b = diagnose(fixture(),prediction)
        self.assertEqual(a,b)
        self.assertEqual(a['next_check']['input_type'],'student_explanation')
        r = fixture()
        r['experiment']['probes'].append({**r['experiment']['probes'][0], 'id':'second'})
        r['measurements'].append({**r['measurements'][0], 'probe_id':'second'})
        r['student_expectations']['second'] = 1
        result = diagnose(r,prediction)
        self.assertEqual(len(result['hypotheses']['concept']['evidence_ids']),2)

    def test_history_does_not_keep_corrected_fault_active(self):
        request = fixture()
        request['student_circuit']['components'][0]['value'] = 2000
        first = advance_session(request,simulator=prediction)
        self.assertEqual(first['result']['hypotheses']['wiring']['support'],'supported')
        second = advance_session(fixture(),first['state'],prediction)
        self.assertEqual(second['result']['hypotheses']['wiring']['support'],'unresolved')
        self.assertEqual(len(second['state']['snapshots']),2)
        again = advance_session(fixture(),second['state'],prediction)
        self.assertTrue(again['unchanged_input'])
        self.assertEqual(len(again['state']['snapshots']),2)
        self.assertEqual(len(first['state']['snapshots']),1)

    def test_localized_directional_fault(self):
        request = json.loads(Path('examples/opamp.json').read_text())
        ref = request['experiment']['circuit']
        got = copy.deepcopy(ref)
        opamp = next(c for c in got['components'] if c['type']=='OPAMP')
        opamp['pins']['+'] = 'input'
        findings = diff(normalize(ref),normalize(got))
        self.assertTrue(any(f['kind']=='missing_connection' for f in findings))
        self.assertTrue(any(f['kind']=='unexpected_connection' for f in findings))

    @patch('reasoning.spice.shutil.which',return_value='ngspice')
    def test_bad_solver_output(self, _):
        r = fixture()
        for output in ('', '159 NaN', '159 -1', '999 0.7', '159 0.7\n160 0.8', '159 0.7 0.1'):
            with self.subTest(output=output):
                def run(argv, **kwargs):
                    Path(kwargs['cwd'],'reading.txt').write_text(output)
                    return subprocess.CompletedProcess(argv,0)
                with patch('reasoning.spice.subprocess.run',side_effect=run):
                    self.assertEqual(simulate(normalize(r['student_circuit']),r['experiment']['probes'][0])['status'],'failed')

    def test_validate_cli(self):
        result = subprocess.run([sys.executable,'-m','reasoning','examples/rc.json','--validate-only'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'valid':True})

    def test_labeled_scenarios(self):
        # Explicit simulated oracle values test reasoning, not ngspice accuracy.
        cases = json.loads(Path('tests/fixtures/diagnostic_cases.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                request = fixture()
                if case.get('concept_expectations') is False:
                    request['student_expectations'] = {}
                for path, value in case['changes']:
                    target = request
                    for part in path[:-1]:
                        target = target[part]
                    target[path[-1]] = value
                if 'measurement' in case:
                    request['measurements'][0]['value'] = case['measurement']
                result = diagnose(request,lambda c,p:{'status':'ok','value':case.get('prediction',.70710678)})
                self.assertEqual(result['next_check']['kind'],case['expected_check'])
                self.assertEqual(sorted(k for k,v in result['hypotheses'].items() if v['support']=='supported'),sorted(case['supported']))
