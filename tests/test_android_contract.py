from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import unittest
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app
from backend.catalog import load_catalog
from backend.config import Settings
from knowledge_lifecycle import Principal


class AndroidContractTests(unittest.TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        settings=Settings(data_dir=Path(self.directory.name),vision_enabled=False,qwen_enabled=False,worker_enabled=False)
        catalog=load_catalog(settings.catalog_path)
        for experiment in catalog.values():experiment['workflow_approved']=True
        self.app=create_app(settings,catalog=catalog,verify=lambda token:Principal(token,'test-lab','student'))
        self.client=TestClient(self.app);self.client.__enter__()
        self.headers={'Authorization':'Bearer synthetic-student','Idempotency-Key':str(uuid4())}
        stream=BytesIO();Image.new('RGB',(8,8),'white').save(stream,format='PNG');self.image=stream.getvalue()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.directory.cleanup()
    def create(self):
        response=self.client.post('/api/v1/sessions',headers=self.headers,json={'experiment_id':'nand-not-example','description':'Synthetic JSON session'})
        self.assertEqual(response.status_code,201,response.text)
        record=response.json();self.url='/api/v1/sessions/'+record['session_id'];return record
    def get(self):return self.client.get(self.url,headers=self.headers).json()
    def upload(self,version=1,headers=None):
        return self.client.post(self.url+'/image',headers=headers or self.headers,data={'expected_session_version':version},files={'image':('synthetic.png',self.image,'image/png')})
    def event(self,kind,payload):
        return self.client.post(self.url+'/events',headers=self.headers,json={'event_id':str(uuid4()),'expected_session_version':self.get()['session_version'],'type':kind,'payload':payload})
    def test_two_step_review_diagnosis_measurements_and_close(self):
        record=self.create()
        self.assertEqual(record['state'],'awaiting_image')
        self.assertIsNone(record['image']);self.assertIsNone(record['job_id'])
        self.assertIn('session_version',record);self.assertNotIn('version',record)
        self.assertFalse(self.app.state.workflow.run_one())
        self.assertEqual(self.client.get(self.url+'/image',headers=self.headers).status_code,404)
        self.assertEqual(self.upload().status_code,202)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['state'],'awaiting_review')
        candidate=json.loads(Path('examples/7400-not.candidate.json').read_text())
        response=self.event('replace_candidate',{'candidate_revision':1,'candidate':candidate})
        self.assertEqual(response.status_code,200,response.text)
        response=self.event('confirm_candidate',{'candidate_revision':2,'acknowledgement':'reviewed_all_connections_and_board'})
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one()
        record=self.get();self.assertIsNone(record['error'],record)
        response=self.event('measurements',{'candidate_revision':2,'measurements':[{'input':0,'output':1},{'input':1,'output':0}],'student_expectations':[]})
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one()
        response=self.event('close_session',{'resolved':True})
        self.assertEqual(response.status_code,200,response.text)
        self.app.state.workflow.run_one()
        self.assertEqual(self.get()['state'],'closed',self.get())
        self.assertEqual(self.event('message',{'text':'after closing'}).status_code,409)
    def test_upload_replay_conflict_and_ownership(self):
        record=self.create()
        replay=self.client.post('/api/v1/sessions',headers=self.headers,json={'experiment_id':'nand-not-example','description':'Synthetic JSON session'})
        self.assertEqual(replay.json()['session_id'],record['session_id'])
        other={**self.headers,'Authorization':'Bearer another-student'}
        self.assertEqual(self.upload(headers=other).status_code,404)
        first=self.upload();self.assertEqual(first.status_code,202,first.text)
        self.app.state.workflow.run_one()
        self.assertEqual(self.upload().json(),first.json())
        self.assertEqual(self.upload(version=2).status_code,409)
        self.assertEqual(self.upload(headers={**self.headers,'Idempotency-Key':str(uuid4())}).status_code,409)
        self.assertEqual(self.get()['state'],'awaiting_review')
    def test_events_are_nested_typed_and_version_checked(self):
        self.create()
        invalid={'event_id':str(uuid4()),'expected_version':1,'type':'message','text':'old flat event'}
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=invalid).status_code,422)
        body={'event_id':str(uuid4()),'expected_session_version':1,'type':'message','payload':{'text':'Hello'}}
        first=self.client.post(self.url+'/events',headers=self.headers,json=body)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=body).json(),first.json())
        body['event_id']=str(uuid4())
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=body).status_code,409)
        self.assertEqual(self.event('message',{'text':'test','diagnostic':{}}).status_code,422)
        self.assertEqual(self.event('complete',{'resolved':True}).status_code,422)
    def test_close_before_image_does_not_write_outcome(self):
        self.create()
        response=self.event('close_session',{})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['state'],'closed')
        self.assertFalse(self.app.state.workflow.run_one())
        self.assertEqual(self.upload(version=response.json()['session_version']).status_code,409)
        with self.app.state.workflow.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
    def test_schema_declares_json_creation_and_nested_payloads(self):
        schema=self.client.get('/openapi.json').json()
        content=schema['paths']['/api/v1/sessions']['post']['requestBody']['content']
        self.assertEqual(set(content),{'application/json'})
        event_schema=schema['components']['schemas']['ConfirmCandidateEvent']
        self.assertIn('payload',event_schema['required'])
        self.assertIn('expected_session_version',event_schema['required'])
        self.assertNotIn('expected_version',event_schema['properties'])
        self.assertIn('multipart/form-data',schema['paths']['/api/v1/sessions/{session_id}/image']['post']['requestBody']['content'])
        self.assertIn('close_session',json.dumps(schema['components']['schemas']['CloseSessionEvent']))

    def test_separate_upload_accepts_more_than_json_body_limit(self):
        import os
        self.create()
        stream=BytesIO()
        Image.frombytes('RGB',(512,512),os.urandom(512*512*3)).save(stream,format='PNG')
        self.image=stream.getvalue()
        self.assertGreater(len(self.image),512*1024)
        response=self.upload()
        self.assertEqual(response.status_code,202,response.text)

    def test_nested_sources_reject_boolean_and_close_replay_is_idempotent(self):
        self.create();self.upload();self.app.state.workflow.run_one()
        response=self.event('source_settings',{'candidate_revision':1,'sources':{'V1':{'dc':False,'ac':1}}})
        self.assertEqual(response.status_code,422,response.text)
        body={'event_id':str(uuid4()),'expected_session_version':self.get()['session_version'],'type':'close_session','payload':{}}
        first=self.client.post(self.url+'/events',headers=self.headers,json=body)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post(self.url+'/events',headers=self.headers,json=body).json(),first.json())

if __name__=='__main__':unittest.main()
