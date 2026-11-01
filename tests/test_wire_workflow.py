from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import unittest
from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.catalog import load_catalog
from backend.config import Settings
from knowledge_lifecycle import Principal
from labvision.core import endpoint, confirm, CandidateError
from reasoning.api import diagnose_input
import test_grid_pipeline as grid_pipeline


class WireReasoningTests(unittest.TestCase):
    def setUp(self):
        item=load_catalog(Settings().catalog_path)[('wire-hole-practice-v1','1')]
        candidate={'schema_version':'0.1','candidate_id':'test','revision':1,
            'reviewed_revision':None,'board_profile_id':item['board']['id'],
            'board_confirmed':False,'components':[],'ports':[],'issues':[],
            'wires':[{'id':w['id'],'a':endpoint(w['a']),'b':endpoint(w['b'])} for w in item['reference']['circuit']['wires']]}
        self.request={'schema_version':'2.0','analysis':'wire_connections',
            'board':item['board'],'reference':item['reference'],'candidate':confirm(candidate,item['board'],1)}

    def test_draft_observations_and_review_gate(self):
        result=diagnose_input(self.request)
        self.assertEqual(result['status'],'evaluated')
        self.assertEqual(result['hypotheses']['wiring']['support'],'unresolved')
        self.assertIn('wire_reference_not_approved',[x['kind'] for x in result['findings']])
        self.request['candidate']['reviewed_revision']=None
        self.assertEqual(diagnose_input(self.request)['status'],'needs_confirmation')

    def test_exact_matching_ignores_wire_names_and_direction(self):
        self.request['reference']['approval']='approved'
        wire=self.request['candidate']['wires'][0]
        wire['id']='Different';wire['a'],wire['b']=wire['b'],wire['a']
        result=diagnose_input(self.request)
        self.assertTrue(result['findings'][-1]['exact_match'])

    def test_same_strip_is_not_same_hole_and_wrong_row_is_detected(self):
        self.request['reference']['approval']='approved'
        self.request['candidate']['wires'][0]['a']['hole']='A5'
        result=diagnose_input(self.request)
        self.assertFalse(result['findings'][-1]['exact_match'])
        self.assertTrue(result['findings'][-1]['strip_pairs_match'])
        self.request['candidate']['wires'][0]['b']['hole']='F6'
        result=diagnose_input(self.request)
        self.assertFalse(result['findings'][-1]['strip_pairs_match'])
        self.assertEqual(result['hypotheses']['wiring']['support'],'supported')

    def test_empty_wires_report_missing_and_invalid_evidence_rejected(self):
        self.request['reference']['approval']='approved'
        self.request['candidate']['wires']=[]
        result=diagnose_input(self.request)
        self.assertEqual(sum(x['kind']=='missing_expected_wire' for x in result['findings']),3)
        self.request['measurements']=[{'voltage':5}]
        with self.assertRaises(CandidateError):diagnose_input(self.request)

    def test_regular_circuit_still_requires_components(self):
        del self.request['board']['capture_mode']
        with self.assertRaises(CandidateError):confirm(self.request['candidate'],self.request['board'],1)

    def test_schema_and_ambiguous_duplicate_unknown_endpoints(self):
        Draft202012Validator(json.loads(Path('schemas/reference-record.schema.json').read_text())).validate(self.request['reference'])
        Draft202012Validator(json.loads(Path('schemas/generalized-response.schema.json').read_text())).validate(diagnose_input(self.request))
        original=deepcopy(self.request)
        self.request['candidate']['wires'][0]['a']['alternatives']=['A5']
        self.assertEqual(diagnose_input(self.request)['status'],'needs_confirmation')
        for hole in ('E12','A99'):
            request=deepcopy(original)
            request['candidate']['wires'][0]['a']['hole']=hole
            with self.assertRaises(CandidateError):diagnose_input(request)


class WireBackendTests(unittest.TestCase):
    def test_public_mp4_grid_wire_review_ml2_ml3_close(self):
        grid_pipeline.GridPipelineTests.setUpClass()
        with TemporaryDirectory() as directory:
            settings=Settings(data_dir=Path(directory),auto_grid_enabled=True,worker_enabled=False,
                vision_enabled=False,qwen_enabled=False)
            app=create_app(settings,verify=lambda token:Principal(token,'test-lab','student'))
            with TestClient(app) as client:
                headers={'Authorization':'Bearer test-student','Idempotency-Key':str(uuid4())}
                catalog=client.get('/api/v1/experiments',headers=headers).json()['experiments']
                item=next(x for x in catalog if x['experiment_id']=='wire-hole-practice-v1')
                self.assertEqual(item['review_contract']['analysis']['engine'],'wire_connections')
                response=client.post('/api/v1/sessions',headers=headers,json={
                    'experiment_id':'wire-hole-practice-v1','description':'Identify my wire connections'})
                self.assertEqual(response.status_code,201,response.text)
                url='/api/v1/sessions/'+response.json()['session_id']
                response=client.post(url+'/image',headers=headers,data={'expected_session_version':1},
                    files={'image':('board.mp4',grid_pipeline.GridPipelineTests.video,'video/mp4')})
                self.assertEqual(response.status_code,202,response.text)
                app.state.workflow.run_one()
                def get():return client.get(url,headers=headers).json()
                def event(kind,payload):
                    response=client.post(url+'/events',headers=headers,json={'event_id':str(uuid4()),
                        'expected_session_version':get()['session_version'],'type':kind,'payload':payload})
                    self.assertEqual(response.status_code,200,response.text)
                    return response.json()
                def binding():
                    r=get()
                    return dict(candidate_revision=r['candidate_revision'],frame_id=r['ml1']['media']['selected_frame_id'],
                        image_sha256=r['image']['sha256'],board_fingerprint=r['ml1']['grid_proposal']['board_fingerprint'])
                self.assertIsNone(get()['error'],get())
                event('accept_grid',{**binding(),'left_top':'A1','right_top':'F1',
                    'acknowledgement':'reviewed_grid_alignment_and_printed_labels'})
                holes=get()['ml1']['grid_proposal']['holes']
                event('add_wire',{**binding(),'wire_id':'W1','a_xy':holes['E5'],'b_xy':holes['F5'],
                    'acknowledgement':'reviewed_same_physical_wire'})
                event('confirm_candidate',{'candidate_revision':get()['candidate_revision'],
                    'acknowledgement':'reviewed_all_connections_and_board'})
                app.state.workflow.run_one()
                result=get()
                self.assertIsNone(result['error'],result)
                self.assertEqual(result['diagnostic']['status'],'evaluated')
                self.assertIsNotNone(result['explanation'])
                self.assertEqual(result['candidate']['components'],[])
                event('close_session',{'resolved':False})
                app.state.workflow.run_one()
                self.assertEqual(get()['state'],'closed')
