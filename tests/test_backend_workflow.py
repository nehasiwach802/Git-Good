from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import unittest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app
from backend.config import Settings
from backend.catalog import load_catalog
from backend.integrations import Integrations
from knowledge_lifecycle import Principal


def png():
    b=BytesIO();Image.new('RGB',(8,8),'white').save(b,format='PNG');return b.getvalue()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.settings=Settings(data_dir=Path(self.temp.name),worker_enabled=False,vision_enabled=False,qwen_enabled=False)
        self.catalog=load_catalog(Path('backend/catalog.json'))
        for x in self.catalog.values():x['workflow_approved']=True
        self.app=create_app(self.settings,catalog=self.catalog,verify=lambda token:Principal(token,'test-lab','student'))
        self.client=TestClient(self.app);self.client.__enter__()
        self.headers={'Authorization':'Bearer test-student','Idempotency-Key':str(uuid4())}
        self.sid=None
    def tearDown(self):
        self.client.__exit__(None,None,None);self.temp.cleanup()
    def upload(self):
        response=self.client.post('/api/v1/sessions',headers=self.headers,data={'experiment_id':'nand-not-example','description':'Synthetic integration check'},files={'image':('test.png',png(),'image/png')})
        self.assertEqual(response.status_code,202,response.text)
        self.sid=response.json()['session_id'];return response.json()
    def get(self):return self.client.get('/api/v1/sessions/'+self.sid,headers=self.headers).json()
    def send(self,kind,**values):
        current=self.get()
        return self.client.post('/api/v1/sessions/'+self.sid+'/events',headers=self.headers,json=dict(type=kind,event_id=str(uuid4()),expected_version=current['version'],**values))
    def reviewed(self):
        self.upload();self.app.state.workflow.run_one()
        candidate=json.loads(Path('examples/7400-not.candidate.json').read_text())
        response=self.send('replace_candidate',candidate_revision=1,candidate=candidate)
        self.assertEqual(response.status_code,200,response.text)
        current=self.get()
        response=self.send('confirm_candidate',candidate_revision=current['candidate_revision'],acknowledgement='reviewed_all_connections_and_board')
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one();return self.get()
    def test_actual_ml1_manual_unknowns_block_confirmation(self):
        self.upload();self.app.state.workflow.run_one()
        self.assertEqual(self.get()['ml1']['mode'],'manual')
        response=self.send('confirm_candidate',candidate_revision=1,acknowledgement='reviewed_all_connections_and_board')
        self.assertEqual(response.status_code,422,response.text)
        self.assertIsNone(self.get()['diagnostic'])
    def test_actual_ml2_ml3_review_measurement_completion(self):
        record=self.reviewed()
        self.assertIsNone(record['error'],record)
        self.assertIsNotNone(record['diagnostic'],record)
        self.assertIsNotNone(record['explanation'],record)
        self.assertIsNone(record['explanation']['cause_probabilities'])
        response=self.send('measurements',candidate_revision=record['candidate_revision'],measurements=[{'input':0,'output':1},{'input':1,'output':0}],student_expectations=[])
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['diagnostic']['status'],'evaluated',self.get())
        response=self.send('complete',resolved=True)
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['state'],'completed',self.get())
    def test_auth_ownership_idempotency_and_stale_versions(self):
        self.assertEqual(self.client.get('/api/v1/experiments').status_code,401)
        initial=self.upload()
        repeated=self.upload();self.assertEqual(initial['session_id'],repeated['session_id'])
        other={'Authorization':'Bearer another-student'}
        self.assertEqual(self.client.get('/api/v1/sessions/'+self.sid,headers=other).status_code,404)
        self.assertEqual(self.client.get('/api/v1/sessions/'+self.sid+'/image',headers=other).status_code,404)
        self.app.state.workflow.run_one()
        payload=dict(type='message',event_id=str(uuid4()),expected_version=self.get()['version'],text='What next?')
        url='/api/v1/sessions/'+self.sid+'/events'
        first=self.client.post(url,headers=self.headers,json=payload)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post(url,headers=self.headers,json=payload).json(),first.json())
        payload['event_id']=str(uuid4())
        self.assertEqual(self.client.post(url,headers=self.headers,json=payload).status_code,409)
    def test_rejected_images_and_no_forged_diagnosis(self):
        response=self.client.post('/api/v1/sessions',headers=self.headers,data={'experiment_id':'nand-not-example','description':'test'},files={'image':('bad.png',b'bad','image/png')})
        self.assertEqual(response.status_code,415)
        self.upload();self.app.state.workflow.run_one()
        self.assertEqual(self.send('diagnose',diagnostic={'status':'evaluated'}).status_code,422)
    def test_durable_queued_jobs_and_explicit_retry_after_crash(self):
        self.upload()
        from backend.store import Store
        store=Store(self.settings.data_dir)
        self.assertEqual(store.claim()['kind'],'extract')
        store.recover()
        self.assertEqual(self.get()['state'],'failed')
        self.assertFalse(self.app.state.workflow.run_one())
        self.assertEqual(self.send('retry_extraction').status_code,200)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['state'],'awaiting_review')

    def test_streamed_limits_image_deletion_and_mounted_ml3_ownership(self):
        self.upload();self.app.state.workflow.run_one()
        url='/api/v1/sessions/'+self.sid
        image=self.client.get(url+'/image',headers=self.headers)
        self.assertEqual(image.content,png())
        self.assertEqual(image.headers['cache-control'],'private, no-store')
        response=self.client.post(url+'/events',headers=self.headers,content=iter([b' '*(300*1024),b' '*(300*1024)]))
        self.assertEqual(response.status_code,413)
        self.assertEqual(self.client.get('/api/v1/ml3/openapi.json').status_code,200)
        body={'query':'test','equipment_id':'unassigned','channel':'unassigned','simulated':True}
        context='/api/v1/ml3/sessions/'+self.sid+'/context'
        self.assertEqual(self.client.post(context,headers=self.headers,json=body).json()['memory_status'],'unavailable')
        self.assertEqual(self.client.post(context,headers={'Authorization':'Bearer another-student'},json=body).status_code,404)
        self.assertEqual(self.client.delete(url,headers=self.headers).status_code,204)
        self.assertEqual(self.client.get(url,headers=self.headers).status_code,404)

    def test_rc_source_settings_and_real_solver(self):
        response=self.client.post('/api/v1/sessions',headers=self.headers,data={'experiment_id':'rc-lowpass-example','description':'Synthetic RC'},files={'image':('test.png',png(),'image/png')})
        self.assertEqual(response.status_code,202,response.text)
        self.sid=response.json()['session_id'];self.app.state.workflow.run_one()
        fixture=json.loads(Path('examples/vision-rc.json').read_text())
        self.assertEqual(self.send('replace_candidate',candidate_revision=1,candidate=fixture['candidate']).status_code,200)
        self.assertEqual(self.send('set_correspondence',component_map=fixture['component_id_map']).status_code,200)
        self.assertEqual(self.send('source_settings',candidate_revision=2,sources={'V1':{'dc':0,'ac':1}}).status_code,200)
        self.assertEqual(self.send('confirm_candidate',candidate_revision=2,acknowledgement='reviewed_all_connections_and_board').status_code,200)
        self.app.state.workflow.run_one()
        record=self.get()
        self.assertIsNone(record['error'],record)
        self.assertEqual(record['diagnostic']['status'],'evaluated',record)
        prediction=record['diagnostic']['predictions'][0]['student']
        self.assertAlmostEqual(prediction['value'],2**-.5,places=6)
        reading={'probe_id':'output','value':2**-.5,'unit':'V','convention':'ac_magnitude'}
        response=self.send('measurements',candidate_revision=2,measurements=[reading],student_expectations={})
        self.assertEqual(response.status_code,200,response.text)

    def test_ml3_preserves_supplied_probabilities_without_inventing_them(self):
        from backend.integrations import diagnostic_result
        from mentor import explain_diagnostic
        record=self.reviewed()
        self.assertEqual(record['explanation']['probability_status'],'not_calibrated')
        probabilities={'wiring':0.7,'concept':0.2,'apparatus':0.1}
        record['diagnostic']['cause_probabilities']=probabilities
        record['diagnostic']['suspected_cause']='wiring'
        explanation=explain_diagnostic(diagnostic_result(record))
        self.assertEqual(explanation['cause_probabilities'],probabilities)
        self.assertEqual(explanation['probability_status'],'provided_by_ml2')
        self.assertIn('70.0%',explanation['explanation'])

    def test_background_worker_processes_upload_without_manual_job_call(self):
        from dataclasses import replace
        import time
        app=create_app(replace(self.settings,worker_enabled=True),catalog=self.catalog,verify=lambda token:Principal(token,'test-lab','student'))
        with TestClient(app) as client:
            response=client.post('/api/v1/sessions',headers=self.headers,data={'experiment_id':'nand-not-example','description':'Worker test'},files={'image':('test.png',png(),'image/png')})
            self.assertEqual(response.status_code,202,response.text)
            url='/api/v1/sessions/'+response.json()['session_id']
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                record=client.get(url,headers=self.headers).json()
                if record['state']!='extracting':break
                time.sleep(.025)
            self.assertEqual(record['state'],'awaiting_review',record)

if __name__=='__main__':unittest.main()
