import copy
import json
import shutil
import unittest
from pathlib import Path
from reasoning.circuit import normalize, diff
from reasoning.engine import diagnose
from reasoning.spice import simulate


def fixture():
    return json.loads(Path('examples/rc.json').read_text())


def fake(circuit, probe):
    return {'status': 'ok', 'value': .70710678}


class ReasoningTests(unittest.TestCase):
    def test_equivalent_labels_and_reversed_passive(self):
        a = fixture()['student_circuit']
        b = copy.deepcopy(a)
        for c in b['components']:
            c['pins'] = {p: {'input':'x','output':'y'}.get(n,n) for p,n in c['pins'].items()}
        b['components'][0]['pins'] = {'1':'y','2':'x'}
        self.assertEqual(diff(normalize(a), normalize(b)), [])

    def test_open_short_missing_wrong_value(self):
        for mutation in ('open','short','missing','value'):
            with self.subTest(mutation=mutation):
                a = fixture()['student_circuit']
                b = copy.deepcopy(a)
                if mutation == 'open': b['components'][0]['pins']['2'] = 'floating'
                if mutation == 'short': b['wires'] = [['output','0']]
                if mutation == 'missing': b['components'].pop(0)
                if mutation == 'value': b['components'][0]['value'] = 2000
                self.assertTrue(diff(normalize(a), normalize(b)))

    def test_wire_aliases(self):
        a = fixture()['student_circuit']
        b = copy.deepcopy(a)
        b['components'][0]['pins']['2'] = 'hole'
        b['wires'] = [['hole','output']]
        self.assertEqual(diff(normalize(a),normalize(b)), [])

    def test_concept_evidence(self):
        result = diagnose(fixture(), fake)
        self.assertEqual(result['hypotheses']['concept']['support'], 'supported')

    def test_mismatch_is_not_apparatus_proof(self):
        r = fixture()
        r['measurements'][0]['value'] = 0
        result = diagnose(r, fake)
        self.assertEqual(result['hypotheses']['apparatus']['support'], 'unresolved')
        r['equipment_evidence'] = {'anomaly_follows_equipment':True,'source_ids':['approved_trial_1']}
        self.assertEqual(diagnose(r,fake)['hypotheses']['apparatus']['support'],'supported')

    def test_confirmation_and_safety_gate(self):
        r = fixture()
        r['student_circuit']['components'][0]['confirmed'] = False
        self.assertEqual(diagnose(r,fake)['status'],'needs_confirmation')
        r.pop('safety_profile')
        self.assertEqual(diagnose(r,fake)['status'],'instructor_required')

    def test_simulation_failure_not_fault(self):
        result = diagnose(fixture(), lambda c,p: {'status':'failed'})
        self.assertEqual(result['next_check']['kind'],'resolve_simulation')
        self.assertEqual(result['hypotheses']['apparatus']['support'],'unresolved')

    def test_invalid_input(self):
        for value in (float('nan'), -1, '1k', True):
            r = fixture()
            r['student_circuit']['components'][0]['value'] = value
            with self.assertRaises(ValueError): diagnose(r,fake)

    def test_wrong_units(self):
        r = fixture()
        r['measurements'][0]['convention'] = 'rms'
        with self.assertRaises(ValueError): diagnose(r,fake)

    def test_missing_executable(self):
        r = fixture()
        self.assertEqual(simulate(normalize(r['student_circuit']), r['experiment']['probes'][0], 'nonexistent-ngspice-test')['status'],'unavailable')

    @unittest.skipUnless(shutil.which('ngspice'), 'ngspice not installed')
    def test_real_rc_and_opamp(self):
        for filename, expected in [('rc',.70710678),('opamp',1.99994)]:
            r = json.loads(Path(f'examples/{filename}.json').read_text())
            p = simulate(normalize(r['student_circuit']),r['experiment']['probes'][0])
            self.assertEqual(p['status'],'ok')
            self.assertAlmostEqual(p['value'],expected,places=4)


if __name__ == '__main__':
    unittest.main()
