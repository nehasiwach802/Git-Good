"""Public Android grid/wire workflow against real video decoding and ML2/ML3."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import unittest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import Settings
from backend.catalog import load_catalog
from knowledge_lifecycle import Principal
import test_grid_pipeline as grid_pipeline


class BackendGridContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        grid_pipeline.GridPipelineTests.setUpClass()
        cls.video=grid_pipeline.GridPipelineTests.video

    def setUp(self):
        self.directory=TemporaryDirectory()
        settings=Settings(data_dir=Path(self.directory.name),auto_grid_enabled=True,
            worker_enabled=False,vision_enabled=False,qwen_enabled=False)
        catalog=load_catalog(settings.catalog_path)
        for item in catalog.values():item['workflow_approved']=True
        self.app=create_app(settings,catalog=catalog,verify=lambda token:Principal(token,'test-lab','student'))
        self.client=TestClient(self.app);self.client.__enter__()
        self.headers={'Authorization':'Bearer synthetic-student','Idempotency-Key':str(uuid4())}
        response=self.client.post('/api/v1/sessions',headers=self.headers,
            json={'experiment_id':'nand-not-example','description':'Synthetic grid and wire review'})
        self.assertEqual(response.status_code,201,response.text)
        self.url='/api/v1/sessions/'+response.json()['session_id']
        response=self.client.post(self.url+'/image',headers=self.headers,
            data={'expected_session_version':1},files={'image':('grid.mp4',self.video,'video/mp4')})
        self.assertEqual(response.status_code,202,response.text)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['ml1']['grid_proposal']['status'],'needs_orientation_review')

    def tearDown(self):
        self.client.__exit__(None,None,None);self.directory.cleanup()

    def get(self):return self.client.get(self.url,headers=self.headers).json()

    def binding(self,record=None):
        record=record or self.get()
        return dict(candidate_revision=record['candidate_revision'],
            frame_id=record['ml1']['media']['selected_frame_id'],image_sha256=record['image']['sha256'],
            board_fingerprint=record['ml1']['grid_proposal']['board_fingerprint'])

    def body(self,kind,payload,record=None):
        record=record or self.get()
        return {'event_id':str(uuid4()),'expected_session_version':record['session_version'],'type':kind,'payload':payload}

    def event(self,kind,payload):
        return self.client.post(self.url+'/events',headers=self.headers,json=self.body(kind,payload))

    def accept(self,left='A30',right='F1'):
        response=self.event('accept_grid',{**self.binding(),'left_top':left,'right_top':right,
            'acknowledgement':'reviewed_grid_alignment_and_printed_labels'})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def xy(self,hole):return self.get()['ml1']['grid_proposal']['holes'][hole]

    def preview(self,xy,**changes):
        request={**self.binding(),'expected_session_version':self.get()['session_version'],'xy':xy,**changes}
        return self.client.post(self.url+'/grid/suggest',headers=self.headers,json=request)

    def test_accept_preview_add_edit_remove_and_final_review(self):
        xy=self.xy('E20')
        original=self.get()
        preview=self.preview(xy)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertIsNone(preview.json()['suggestion']['hole'])
        self.assertEqual(self.get(),original)  # Preview does not change session version.
        accepted=self.accept()
        self.assertEqual(accepted['candidate_revision'],2)
        self.assertIsNone(accepted['candidate']['reviewed_revision'])
        preview=self.preview(xy).json()['suggestion']
        self.assertEqual(preview['hole'],'E11');self.assertFalse(preview['confirmed'])
        response=self.event('add_wire',{**self.binding(),'wire_id':'Wnew','a_xy':xy,'b_xy':self.xy('F20'),
            'acknowledgement':'reviewed_same_physical_wire'})
        self.assertEqual(response.status_code,200,response.text)
        wire=response.json()['candidate']['wires'][-1]
        self.assertEqual((wire['a']['hole'],wire['b']['hole']),('E11','F20'))
        self.assertTrue(wire['pairing_reviewed']);self.assertFalse(wire['a']['confirmed'])
        response=self.event('tap_endpoint',{**self.binding(),'target':'Wnew.b','xy':self.xy('F21')})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['candidate']['wires'][-1]['b']['hole'],'F21')
        response=self.event('remove_wire',{'candidate_revision':self.get()['candidate_revision'],'wire_id':'Wnew'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(any(w['id']=='Wnew' for w in response.json()['candidate']['wires']))
        # Existing complete circuit review and actual ML2 -> ML3 still work.
        fixture=json.loads(Path('examples/7400-not.candidate.json').read_text())
        response=self.event('replace_candidate',{'candidate_revision':self.get()['candidate_revision'],'candidate':fixture})
        self.assertEqual(response.status_code,200,response.text)
        response=self.event('confirm_candidate',{'candidate_revision':self.get()['candidate_revision'],
            'acknowledgement':'reviewed_all_connections_and_board'})
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one();record=self.get()
        self.assertIsNone(record['error'],record)
        self.assertIsNotNone(record['diagnostic']);self.assertIsNotNone(record['explanation'])
        self.assertNotIn('grid_proposal',json.dumps(record['diagnostic']))
        response=self.event('close_session',{'resolved':False})
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one();self.assertEqual(self.get()['state'],'closed')

    def test_event_replay_conflict_and_stale_bindings(self):
        body=self.body('accept_grid',{**self.binding(),'left_top':'A30','right_top':'F1',
            'acknowledgement':'reviewed_grid_alignment_and_printed_labels'})
        response=self.client.post(self.url+'/events',headers=self.headers,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=body).json(),response.json())
        body['payload']['left_top']='A1'
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=body).status_code,409)
        for changes in ({'candidate_revision':1},{'frame_id':'F6'},{'image_sha256':'0'*64},{'board_fingerprint':'0'*64}):
            request={**self.binding(),**changes,'target':'U1.1','xy':self.xy('A1')}
            self.assertEqual(self.event('tap_endpoint',request).status_code,409,changes)
        self.assertEqual(self.preview(self.xy('A1'),expected_session_version=1).status_code,409)

    def test_reject_grid_preserves_manual_correction_and_disables_physical_snap(self):
        self.accept()
        response=self.event('reject_grid',self.binding())
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('grid_review',response.json()['ml1']['media'])
        self.assertTrue(response.json()['ml1']['media']['grid_rejected'])
        response=self.event('tap_endpoint',{**self.binding(),'target':'U1.1','xy':self.xy('A1')})
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(response.json()['detail']['code'],'grid_acceptance_required')
        response=self.event('correct_endpoint',{'candidate_revision':self.get()['candidate_revision'],
            'target':'U1.1','hole':'A1'})
        self.assertEqual(response.status_code,200,response.text)
        record=self.accept();self.assertNotIn('grid_rejected',record['ml1']['media'])

    def test_ambiguous_invalid_and_occupied_taps_are_atomic(self):
        self.accept('A1','F1')
        a,b=self.xy('A10'),self.xy('B10')
        midpoint=[(x+y)/2 for x,y in zip(a,b)]
        original=self.get()
        response=self.event('add_wire',{**self.binding(),'wire_id':'Wnew','a_xy':a,'b_xy':midpoint,
            'acknowledgement':'reviewed_same_physical_wire'})
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(response.json()['detail']['code'],'ambiguous_tap')
        self.assertEqual(self.get(),original)
        for xy in ([-1,0],[self.get()['image']['width'],0],[True,0],['10',20],[0,0,0]):
            response=self.event('tap_endpoint',{**self.binding(),'target':'U1.1','xy':xy})
            self.assertEqual(response.status_code,422,response.text)
        for payload in ({'wire_id':'Wnew','a_xy':a,'b_xy':a},
                        {'wire_id':'U1','a_xy':a,'b_xy':b}):
            response=self.event('add_wire',{**self.binding(),**payload,'acknowledgement':'reviewed_same_physical_wire'})
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.get(),original)
        bad={**self.binding(),'wire_id':'Wnew','a_xy':a,'b_xy':b,'acknowledgement':'reviewed_same_physical_wire',
             'verified_label_map':{'A1':'A1'}}
        self.assertEqual(self.event('add_wire',bad).status_code,422)

    def test_owner_auth_and_capability_contract(self):
        capabilities=self.client.get('/api/v1/capabilities',headers=self.headers).json()
        self.assertTrue(capabilities['grid_review']['enabled'])
        self.assertEqual(capabilities['grid_review']['contract'],'grid-review-1')
        path=self.url+'/grid/suggest'
        body={**self.binding(),'expected_session_version':self.get()['session_version'],'xy':self.xy('A1')}
        self.assertEqual(self.client.post(path,json=body).status_code,401)
        self.assertEqual(self.client.post(path,json=body,headers={'Authorization':'Bearer stranger'}).status_code,404)
        request=self.body('accept_grid',{**self.binding(),'left_top':'A30','right_top':'F1',
            'acknowledgement':'reviewed_grid_alignment_and_printed_labels'})
        self.assertEqual(self.client.post(self.url+'/events',json=request,
            headers={'Authorization':'Bearer stranger'}).status_code,404)
        self.assertEqual(self.client.post(path,headers={**self.headers,'Content-Type':'application/json'},
            content=b'{"xy":[NaN,0]}').status_code,400)
