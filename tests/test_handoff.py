import copy
import json
import unittest
from pathlib import Path
from reasoning.handoff import prepare_reasoning_request
from reasoning.engine import diagnose
from reasoning.session import advance_session
from reasoning.validation import ValidationError


def fixture():
    return json.loads(Path('examples/rc.json').read_text())


def prediction(circuit, probe):
    return {'status':'ok','value':.70710678}


class HandoffTests(unittest.TestCase):
    def test_identity_and_pin_mapping_preserves_actual_wiring(self):
        request = fixture()
        source = request['student_circuit']['components'][0]
        source['id'] = 'detected_resistor'
        source['pins'] = {'left':'input','right':'wrong_net'}
        source['confirmed'] = False
        original = copy.deepcopy(request)
        adapted = prepare_reasoning_request(request,
            component_id_map={'detected_resistor':'R1'},
            pin_maps={'detected_resistor':{'left':'1','right':'2'}})
        self.assertEqual(request,original)
        part = adapted['student_circuit']['components'][0]
        self.assertEqual(part['pins']['2'],'wrong_net')
        self.assertFalse(part['confirmed'])
        self.assertEqual(diagnose(adapted,prediction)['status'],'needs_confirmation')
        part['confirmed'] = True
        self.assertEqual(diagnose(adapted,prediction)['hypotheses']['wiring']['support'],'supported')

    def test_bad_identity_and_pin_maps(self):
        for mapping in ({'unknown':'R1'}, {'R1':'missing'}, {'R1':'C1'}):
            with self.subTest(mapping=mapping):
                with self.assertRaises(ValueError):
                    prepare_reasoning_request(fixture(),component_id_map=mapping)
        for pins in ({'1':'1'}, {'1':'1','2':'1'}, {'1':'1','2':2}):
            with self.assertRaises(ValueError):
                prepare_reasoning_request(fixture(),component_id_map={},pin_maps={'R1':pins})

    def test_stale_review_blocks_solver(self):
        request = fixture()
        request['source_context'] = {'board_id':'synthetic_board','candidate_revision':2,'reviewed_revision':1}
        def forbidden(*args):
            self.fail('stale review must not run simulation')
        result = diagnose(request,forbidden)
        self.assertEqual(result['status'],'needs_confirmation')
        self.assertEqual(result['source_context']['candidate_revision'],2)
        request['source_context']['reviewed_revision']=2
        self.assertEqual(diagnose(request,prediction)['status'],'evaluated')

    def test_malformed_source_context(self):
        for source in ({},None,{'board_id':'b','candidate_revision':True,'reviewed_revision':1}):
            request=fixture()
            request['source_context']=source
            with self.assertRaises(ValidationError): diagnose(request,prediction)

    def test_board_and_revision_session_boundaries(self):
        request=fixture()
        request['source_context']={'board_id':'b','candidate_revision':2,'reviewed_revision':2}
        first=advance_session(request,simulator=prediction)
        for source in (None,{'board_id':'other','candidate_revision':2,'reviewed_revision':2},
                       {'board_id':'b','candidate_revision':1,'reviewed_revision':1}):
            altered=copy.deepcopy(request)
            if source is None: altered.pop('source_context')
            else: altered['source_context']=source
            with self.assertRaises(ValueError): advance_session(altered,first['state'],prediction)

    def test_draft_export_and_digital_parts_are_explicitly_rejected(self):
        with self.assertRaises(ValidationError) as error:
            diagnose({'schema_version':'0.1','status':'reviewed_connectivity'})
        self.assertEqual(error.exception.code,'vision_conversion_required')
        request=fixture()
        request['student_circuit']['components'][0]['type']='7400'
        with self.assertRaises(ValidationError) as error:
            diagnose(request,prediction)
        self.assertEqual(error.exception.code,'unsupported_component_model')

    def test_failed_reference_does_not_support_apparatus(self):
        request=fixture()
        request['measurements'][0]['value']=0
        request['equipment_evidence']={'anomaly_follows_equipment':True,'source_ids':['simulated_trial']}
        values=iter([{'status':'failed'},prediction(None,None)])
        result=diagnose(request,lambda c,p:next(values))
        self.assertEqual(result['hypotheses']['apparatus']['support'],'unresolved')
