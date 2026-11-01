"""Video transport integration through the unchanged Android API1.1 surface."""
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
from PIL import Image
import test_android_contract as contracts
from reasoning.media import MediaError


class VideoBackendTests(unittest.TestCase):
    def setUp(self):
        self.flow=contracts.AndroidContractTests();self.flow.setUp()
        self.flow.create()
        self.client=self.flow.client;self.headers=self.flow.headers
        self.store=self.flow.app.state.workflow.store
    def tearDown(self):self.flow.tearDown()
    def files(self):return list((self.store.directory/'video-sources').glob('*.mp4'))

    def test_video_assets_are_private_and_review_image_is_a_selected_jpeg(self):
        response=self.flow.upload();self.assertEqual(response.status_code,202,response.text)
        self.assertIsNone(response.json()['image'])
        self.assertEqual(len(self.files()),1)
        self.flow.app.state.workflow.run_one()
        record=self.flow.get()
        self.assertEqual(record['state'],'awaiting_review',record)
        self.assertEqual(record['image']['content_type'],'image/jpeg')
        self.assertEqual(len(record['ml1']['media']['frames']),6)
        self.assertIsNone(record['candidate']['reviewed_revision'])
        payload=json.dumps(record)
        for private in ('jpeg_bytes','video-sources',str(self.store.directory)):
            self.assertNotIn(private,payload)
        selected=self.client.get(self.flow.url+'/image',headers=self.headers)
        self.assertEqual(selected.status_code,200)
        self.assertEqual(selected.headers['content-type'],'image/jpeg')
        with Image.open(BytesIO(selected.content)) as picture:self.assertEqual(picture.format,'JPEG')
        stranger={**self.headers,'Authorization':'Bearer another-student'}
        self.assertEqual(self.client.get(self.flow.url+'/image',headers=stranger).status_code,404)
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM media_frames').fetchone()[0],6)

    def test_images_and_wrong_video_content_type_are_rejected(self):
        for mime,data in [('image/png',b'not-a-video'),('application/octet-stream',self.flow.video),('video/mp4',b'not-an-mp4')]:
            with self.subTest(mime=mime):
                result=self.client.post(self.flow.url+'/image',headers=self.headers,data={'expected_session_version':1},files={'image':('capture.mp4',data,mime)})
                self.assertEqual(result.status_code,415,result.text)
                self.assertEqual(self.files(),[])
        self.assertEqual(self.flow.get()['state'],'awaiting_image')

    def test_old_image_upload_routes_are_retired(self):
        for path in ('/api/sessions','/api/legacy/v1/sessions'):
            response=self.client.post(path,headers=self.headers,
                data={'experiment_id':'nand-not-example','description':'No photo uploads'},
                files={'image':('photo.png',b'photo','image/png')})
            self.assertEqual(response.status_code,410,response.text)

    def test_idempotency_conflict_and_deletion_clean_private_media(self):
        first=self.flow.upload();self.assertEqual(first.status_code,202,first.text)
        self.flow.app.state.workflow.run_one()
        self.assertEqual(self.flow.upload().json(),first.json())
        self.assertEqual(len(self.files()),1)
        result=self.flow.upload(version=self.flow.get()['session_version'],headers={**self.headers,'Idempotency-Key':str(uuid4())})
        self.assertEqual(result.status_code,409,result.text);self.assertEqual(len(self.files()),1)
        self.assertEqual(self.client.delete(self.flow.url,headers=self.headers).status_code,204)
        self.assertEqual(self.files(),[])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM media_frames').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM session_media').fetchone()[0],0)

    def test_decoder_deadline_and_explicit_retry_keep_original_source(self):
        self.flow.upload()
        with patch.object(self.flow.app.state.workflow.integrations,'extract_video',side_effect=MediaError('video_processing_timeout')):
            self.flow.app.state.workflow.run_one()
        self.assertEqual(self.flow.get()['state'],'failed')
        self.assertEqual(self.flow.get()['error']['code'],'video_processing_timeout')
        self.assertEqual(len(self.files()),1)
        response=self.flow.event('retry_extraction',{})
        self.assertEqual(response.status_code,200,response.text)
        self.flow.app.state.workflow.run_one()
        self.assertEqual(self.flow.get()['state'],'awaiting_review',self.flow.get())

    def test_corrupt_mp4_fails_in_worker_without_private_errors(self):
        video=b'\x00\x00\x00\x18ftypisom'+b'\x00'*32
        result=self.client.post(self.flow.url+'/image',headers=self.headers,data={'expected_session_version':1},files={'image':('capture.mp4',video,'video/mp4')})
        self.assertEqual(result.status_code,202,result.text)
        self.flow.app.state.workflow.run_one()
        record=self.flow.get();self.assertEqual(record['state'],'failed')
        self.assertEqual(record['error']['code'],'invalid_video_or_limits')
        self.assertNotIn(str(self.store.directory),json.dumps(record))

    def test_upload_body_is_bounded_even_without_content_length(self):
        boundary='bounded-test'
        first=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="capture.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode()
        def stream():
            yield first
            for _ in range(52):yield b'x'*(1024*1024)
            yield f'\r\n--{boundary}--\r\n'.encode()
        response=self.client.post(self.flow.url+'/image',headers={**self.headers,'Content-Type':'multipart/form-data; boundary='+boundary},content=stream())
        self.assertEqual(response.status_code,413,response.text)
        self.assertEqual(self.files(),[])

    def test_android_route_fields_and_event_envelope_are_preserved(self):
        schema=self.client.get('/openapi.json').json()
        path='/api/v1/sessions/{session_id}/image'
        self.assertNotIn('/api/v1/sessions/{session_id}/video',schema['paths'])
        ref=schema['paths'][path]['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'].split('/')[-1]
        body=schema['components']['schemas'][ref]
        self.assertEqual(set(body['properties']),{'image','expected_session_version'})
        self.assertEqual(set(body['required']),{'image','expected_session_version'})
        event=schema['components']['schemas']['CloseSessionEvent']
        self.assertEqual(set(event['properties']),{'event_id','expected_session_version','type','payload'})
        self.assertEqual(schema['info']['version'],'1.1.0')
