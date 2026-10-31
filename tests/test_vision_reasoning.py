import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from reasoning.api import diagnose_input, validate_input
from reasoning.validation import ValidationError
from labvision.core import CandidateError, compile_netlist, confirm, correct
from labvision.digital import check_not


def load(name='vision-7400'):
    return json.loads(Path(f'examples/{name}.json').read_text())


class VisionReasoningTests(unittest.TestCase):
    def test_actual_reviewed_export_and_logic(self):
        request=load()
        result=diagnose_input(request)
        self.assertEqual(result['status'],'evaluated')
        self.assertTrue(result['logic_check']['topology_matches'])
        self.assertEqual(result['next_check']['kind'],'review_learning_objective')
        exported=compile_netlist(request['candidate'],request['board'])
        self.assertEqual(result['reviewed_connectivity'],exported)
        self.assertEqual(len(result['findings']),2)

    def test_unreviewed_and_corrected_circuit(self):
        for name in ('vision-7400-unreviewed','vision-7400-wrong-wire'):
            result=diagnose_input(load(name))
            self.assertEqual(result['next_check']['kind'], 'confirm_connections' if name.endswith('unreviewed') else 'review_wiring')
        r=load()
        r['candidate']=correct(r['candidate'],r['board'],'W1.b','A17',1)
        self.assertEqual(diagnose_input(r)['status'],'needs_confirmation')
        r['candidate']=confirm(r['candidate'],r['board'],2)
        self.assertFalse(diagnose_input(r)['logic_check']['topology_matches'])

    def test_binary_mismatch_is_not_equipment_proof(self):
        r=load()
        r['measurements'][0]['output']=0
        result=diagnose_input(r)
        self.assertEqual(result['next_check']['kind'],'instructor_supervised_setup_check')
        self.assertEqual(result['hypotheses']['apparatus']['support'],'unresolved')

    def test_concept_and_missing_measurements(self):
        r=load();r['student_expectations'][0]['output']=0
        self.assertEqual(diagnose_input(r)['hypotheses']['concept']['support'],'supported')
        r['measurements']=[]
        self.assertEqual(diagnose_input(r)['next_check']['kind'],'record_approved_measurement')

    def test_unknowns_and_alternatives_do_not_self_confirm(self):
        for field,value in [('hole',None),('alternatives',['E9']),('confirmed',False)]:
            r=load();r['candidate']['components'][0]['pins']['1'][field]=value
            self.assertEqual(diagnose_input(r)['status'],'needs_confirmation')

    def test_malformed_inputs(self):
        mutations=[
            lambda r:r.update(analysis=[]),
            lambda r:r.update(gate=True),
            lambda r:r.update(gate=5),
            lambda r:r.update(candidate=[]),
            lambda r:r.update(measurements=[{'input':0,'output':2}]),
            lambda r:r.update(measurements=[{'input':False,'output':1}]),
            lambda r:r.update(measurements=[{'input':0,'output':1}]*2),
            lambda r:r.update(student_expectations={'0':1}),
            lambda r:r['candidate'].update(revision=True),
            lambda r:r['board'].update(groups=[['A1'],['A1']]),
            lambda r:r['candidate']['ports'][0].update(endpoint=[]),
            lambda r:r.update(component_id='missing'),
        ]
        for mutate in mutations:
            r=load();mutate(r)
            with self.subTest(mutation=mutate):
                with self.assertRaises(ValidationError):diagnose_input(r)

    def test_supply_short_and_port_alias(self):
        r=load()
        r['candidate']['ports'][-1]['endpoint']['hole']=r['candidate']['ports'][-2]['endpoint']['hole']
        result=diagnose_input(r)
        self.assertFalse(result['logic_check']['topology_matches'])
        self.assertFalse(result['logic_check']['truth_table'])

    def test_extra_load_is_unsupported_not_proof_of_wrong_wiring(self):
        from labvision.core import endpoint
        r=load()
        r['candidate']['components'].append({'id':'LED1','part':'led','identity_confirmed':True,
            'pins':{'anode':{**endpoint('A20'),'confirmed':True},'cathode':{**endpoint('A21'),'confirmed':True}}})
        r['candidate']['revision']=2;r['candidate']['reviewed_revision']=2
        result=diagnose_input(r)
        self.assertEqual(result['status'],'instructor_required')
        self.assertEqual(result['hypotheses']['wiring']['support'],'unresolved')
        self.assertNotIn('logic_check',result)

    def test_all_four_7400_gate_pinouts(self):
        # Exercise logical pin semantics on a synthetic compiled netlist, not
        # plausible photo geometry. The supply pins stay fixed.
        from labvision.core import NAND_GATES
        r=load();net=compile_netlist(r['candidate'],r['board'])
        original=copy.deepcopy(net['components'][0]['pins'])
        for index, selected in enumerate(NAND_GATES,1):
            copy_net=copy.deepcopy(net)
            pins=copy_net['components'][0]['pins']
            a,b,y=NAND_GATES[0]
            for old,new in zip((a,b,y),selected):
                pins[old],pins[new]=original[new],original[old]
            self.assertTrue(check_not(copy_net,gate=index)['topology_matches'])

    def test_analog_conversion_real_solver(self):
        result=diagnose_input(load('vision-rc'))
        self.assertEqual(result['status'],'evaluated')
        self.assertEqual(result['hypotheses']['wiring']['support'],'unresolved')
        predicted=result['predictions'][0]['student']
        self.assertEqual(predicted['status'],'ok')
        self.assertAlmostEqual(predicted['value'],2**-.5,places=6)
        self.assertEqual(result['next_check']['kind'],'explain_prediction')

    def test_bad_analog_configuration(self):
        mutations=[lambda r:r.update(ground_port='OUT'),
                   lambda r:r.update(probe_ports={}),
                   lambda r:r.update(voltage_sources=[]),
                   lambda r:r['voltage_sources'][0].update(ac=float('nan')),
                   lambda r:r['voltage_sources'][0].update(positive_port='missing'),
                   lambda r:r.update(component_id_map=[])]
        for mutate in mutations:
            r=load('vision-rc');mutate(r)
            with self.assertRaises(ValidationError):validate_input(r)

    def test_cli_dummy_output(self):
        run=subprocess.run([sys.executable,'-m','reasoning','examples/vision-7400.json'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue(json.loads(run.stdout)['logic_check']['topology_matches'])

    def test_demo_saves_real_outputs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'demo-output'
            run=subprocess.run([sys.executable,'tools/demo.py','--out',str(target)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(len(list(target.glob('*.json'))),4)
            result=json.loads((target/'vision-rc.json').read_text())
            self.assertEqual(result['predictions'][0]['student']['status'],'ok')

    def test_boolean_revision_not_accepted_as_review(self):
        r=load()
        with self.assertRaises(CandidateError):confirm(r['candidate'],r['board'],True)

    def test_session_review_update_and_revision_replay(self):
        from reasoning.session import advance_session
        request=load('vision-7400-unreviewed')
        first=advance_session(request)
        self.assertEqual(first['result']['status'],'needs_confirmation')
        request['candidate']=confirm(request['candidate'],request['board'],1)
        second=advance_session(request,first['state'])
        self.assertEqual(second['result']['status'],'evaluated')
        edited=copy.deepcopy(request)
        edited['candidate']['wires'][0]['b']['hole']='A17'
        with self.assertRaisesRegex(ValueError,'incrementing revision'):
            advance_session(edited,second['state'])
        edited['candidate']=correct(request['candidate'],request['board'],'W1.b','A17',1)
        third=advance_session(edited,second['state'])
        self.assertEqual(third['result']['status'],'needs_confirmation')
        with self.assertRaisesRegex(ValueError,'stale candidate'):
            advance_session(request,third['state'])
        other=copy.deepcopy(request)
        other['candidate']['candidate_id']='another-candidate'
        with self.assertRaisesRegex(ValueError,'identity changes'):
            advance_session(other,second['state'])
