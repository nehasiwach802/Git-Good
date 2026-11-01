from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
import cv2
import numpy as np
from labvision.core import confirm,make_board
from labvision.handoff import reasoning_input
from labvision.upload import extract_upload
from reasoning.media import normalize_video,process_video,process_image,restore_capture,MediaError,image_receipt
from reasoning.api import diagnose_input,validate_input
from reasoning.session import advance_session
from reasoning.validation import ValidationError


def jpeg(color):
    stream=BytesIO();Image.new('RGB',(16,12),color).save(stream,format='JPEG');return stream.getvalue()


def fixture():
    board=json.loads(Path('examples/board-30.json').read_text())
    frames=[]
    for i,color in enumerate(('white','black'),1):
        data=jpeg(color);receipt=image_receipt(data)
        frames.append({'id':'F'+str(i),'jpeg_bytes':data,**receipt,'decoded_size':[16,12],
            'frame_index':i-1,'timestamp_s':(i-1)/10,'timestamp_source':'decoder_pts',
            'sharpness':float(i),'endpoint_detection':{'status':'disabled'}})
    with patch.dict(os.environ,{'LABVISION_ENDPOINT_WEIGHTS':''}):
        ml1=extract_upload(frames[0]['jpeg_bytes'],board,known_parts=['7400'],try_vision=False)
    return {'schema_version':'ml1-video-1','status':'needs_circuit_review','frames':frames,
        'selected_frame_id':'F1','selection':'explicit_frame_id','ml1':ml1,
        'video':{'sha256':sha256(b'synthetic-video').hexdigest(),'size_bytes':15,'fps':10.,'duration_s':.2,'frame_count':2}},board


def reviewed(capture):
    candidate=json.loads(Path('examples/7400-not.candidate.json').read_text())
    candidate.update(candidate_id=capture.candidate['candidate_id'],revision=capture.candidate['revision'],image_sha256=capture.image['sha256'])
    capture.candidate=candidate
    return capture.confirm(candidate['revision'],acknowledgement='reviewed_all_connections_and_board')


class MediaPipelineTests(unittest.TestCase):
    def test_normalizes_assets_and_json_safe_metadata_without_auto_review(self):
        result,board=fixture();capture=normalize_video(result,board)
        self.assertIsNone(capture.candidate['reviewed_revision'])
        self.assertEqual(capture.image['sha256'],sha256(capture.image_bytes).hexdigest())
        payload=json.dumps(capture.snapshot(),allow_nan=False)
        self.assertNotIn('jpeg_bytes',payload)
        self.assertNotIn('private_path',payload)
        with TemporaryDirectory() as directory:
            assets=capture.persist_assets(directory)
            restored=restore_capture(capture.snapshot(),lambda digest:(Path(directory)/digest).read_bytes())
            self.assertEqual(restored.snapshot(),capture.snapshot())
            self.assertEqual(capture.persist_assets(directory),assets)
            for asset in assets:self.assertEqual(sha256((Path(directory)/asset['asset_id']).read_bytes()).hexdigest(),asset['asset_id'])
            (Path(directory)/assets[0]['asset_id']).write_bytes(b'tampered')
            with self.assertRaisesRegex(MediaError,'stored_asset_hash_mismatch'):capture.persist_assets(directory)

    def test_hash_dimensions_candidate_and_frame_identity_rejections(self):
        result,board=fixture()
        mutations=[lambda r:r['frames'][0].update(sha256='0'*64),
            lambda r:r['frames'][0].update(width=17),
            lambda r:r['ml1']['candidate'].update(image_sha256='0'*64),
            lambda r:r.update(selected_frame_id='F6'),
            lambda r:r['frames'][1].update(id='F1'),
            lambda r:r['frames'][0].update(timestamp_s=float('nan')),
            lambda r:r['video'].update(duration_s=61)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value=deepcopy(result);mutate(value)
                with self.assertRaises(MediaError):normalize_video(value,board)

    def test_frame_switch_clears_calibration_review_and_preserves_identity(self):
        result,board=fixture();capture=reviewed(normalize_video(result,board));capture.calibration={'image':'old'}
        with patch.dict(os.environ,{'LABVISION_ENDPOINT_WEIGHTS':''}):next_capture=capture.select_frame('F2')
        self.assertEqual(next_capture.candidate['revision'],2)
        self.assertEqual(next_capture.candidate['candidate_id'],capture.candidate['candidate_id'])
        self.assertIsNone(next_capture.candidate['reviewed_revision']);self.assertIsNone(next_capture.calibration)
        self.assertNotEqual(next_capture.image['sha256'],capture.image['sha256'])
        self.assertTrue(all(p['hole'] is None for c in next_capture.candidate['components'] for p in c['pins'].values()))
        self.assertEqual(next_capture.select_frame('F2').candidate['revision'],2)
        record={'candidate':capture.candidate,'diagnostic':{'old':'diagnosis'},'explanation':{'old':'explanation'},
            'measurements':[{'old':'reading'}],'component_map':{'U1':'U1'},'student_expectations':[]}
        updated=next_capture.apply_to_record(record)
        self.assertIsNone(updated['diagnostic']);self.assertIsNone(updated['explanation'])
        self.assertEqual(updated['measurements'],[]);self.assertEqual(updated['component_map'],{})
        self.assertEqual(record['diagnostic'],{'old':'diagnosis'})

    def test_ml3_diagnostic_contract_and_existing_predictions_are_unchanged(self):
        result,board=fixture();capture=reviewed(normalize_video(result,board))
        original=json.loads(Path('examples/generalized/ml1-7400.json').read_text())
        context={'safety_profile':'instructor_approved_low_voltage','measurements':[{'input':0,'output':1},{'input':1,'output':0}],'student_expectations':[]}
        expected=diagnose_input({'schema_version':'2.0','reference':original['reference'],
            'input':reasoning_input(capture.candidate,board),'component_map':{'U1':'U1'},**context})
        actual=capture.diagnose(original['reference'],{'U1':'U1'},**context)
        self.assertEqual(actual,expected)
        self.assertNotIn('media',actual);self.assertNotIn('frames',actual);self.assertNotIn('candidate',actual)

    def test_same_revision_cannot_change_only_media_binding(self):
        result,board=fixture();capture=reviewed(normalize_video(result,board))
        reference=json.loads(Path('examples/generalized/ml1-7400.json').read_text())['reference']
        request=capture.request(reference,{'U1':'U1'},safety_profile='instructor_approved_low_voltage')
        first=advance_session(request)
        changed=deepcopy(request);changed['observation']['source']['media_binding']['frame_id']='F2'
        with self.assertRaisesRegex(ValueError,'without incrementing'):advance_session(changed,first['state'])
        changed['observation'].update(revision=2,reviewed_revision=None,completeness_confirmed=False)
        result=advance_session(changed,first['state'])['result']
        self.assertEqual(result['status'],'needs_confirmation')

    def test_image_uses_same_pipeline_and_bound_asset_restore(self):
        _,board=fixture()
        with patch.dict(os.environ,{'LABVISION_ENDPOINT_WEIGHTS':''}):capture=process_image(jpeg('white'),board,known_parts=['7400'])
        self.assertEqual(capture.media['kind'],'image')
        self.assertIsNone(capture.candidate['reviewed_revision'])
        state=capture.snapshot();state['candidate']['image_sha256']='0'*64
        with self.assertRaisesRegex(MediaError,'candidate_image_mismatch'):restore_capture(state,lambda digest:capture.image_bytes)

    def test_decoder_deadline_is_enforced_and_errors_do_not_expose_stderr(self):
        _,board=fixture()
        with TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.avi';path.write_bytes(b'synthetic')
            with patch('reasoning.media.subprocess.run',side_effect=subprocess.TimeoutExpired('private command',1)):
                with self.assertRaisesRegex(MediaError,'video_processing_timeout'):process_video(path,board,deadline_s=1)
            with patch('reasoning.media.subprocess.run',return_value=subprocess.CompletedProcess([],1,stderr='private decoder output')):
                with self.assertRaisesRegex(MediaError,'video_processing_failed') as caught:process_video(path,board)
                self.assertNotIn('private',str(caught.exception))

    def test_real_synthetic_video_decoder_to_reviewed_diagnosis(self):
        _,board=fixture()
        with TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.avi'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,48))
            self.assertTrue(writer.isOpened())
            for i in range(12):writer.write(np.full((48,64,3),i*15,dtype=np.uint8))
            writer.release()
            with patch.dict(os.environ,{'LABVISION_ENDPOINT_WEIGHTS':''}):capture=process_video(path,board,known_parts=['7400'],deadline_s=30)
            self.assertEqual(len(capture.frames),6)
            self.assertEqual(capture.image['sha256'],sha256(capture.image_bytes).hexdigest())
            reviewed(capture)
            reference=json.loads(Path('examples/generalized/ml1-7400.json').read_text())['reference']
            diagnostic=capture.diagnose(reference,{'U1':'U1'},safety_profile='instructor_approved_low_voltage')
            self.assertEqual(diagnostic['status'],'evaluated')


class ExtendedHandoffTests(unittest.TestCase):
    def candidate(self,part):
        from labvision.annotation import new_session,add_component
        board=make_board(30)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.jpg';path.write_bytes(jpeg('white'))
            session=new_session(path,[16,12],board,'synthetic')
        add_component(session,part,'X1')
        candidate=session['candidate']
        for i,p in enumerate(candidate['components'][0]['pins'].values(),1):p['hole']='A'+str(i)
        candidate['ports']=[{'id':'P','role':'input','endpoint':deepcopy(next(iter(candidate['components'][0]['pins'].values())))}]
        return candidate,board

    def test_new_ml1_adapter_keeps_diode_explicitly_unsupported(self):
        candidate,board=self.candidate('diode')
        candidate=confirm(candidate,board,candidate['revision'])
        request={'schema_version':'2.0','reference':{'experiment_id':'diode-connectivity','version':'1','approval':'approved',
            'circuit':{'components':[{'id':'D1','type':'DIODE','pins':{'anode':'a','cathode':'b'}}]},'ports':{},'analysis':{'engine':'connectivity'}},
            'input':{'adapter':'ml1','payload':{'candidate':candidate,'board':board}},'component_map':{'X1':'D1'},'safety_profile':'instructor_approved_low_voltage'}
        result=diagnose_input(request)
        self.assertEqual(result['status'],'unsupported_analysis')
        self.assertTrue(any(g.get('model')=='DIODE' for g in result['capability_gaps']))
        request['input']['adapter']='ml1_v0.1'
        with self.assertRaises(ValidationError):validate_input(request)

    def test_opamp_requires_explicit_gain_not_a_photo_guess(self):
        candidate,board=self.candidate('opamp');candidate=confirm(candidate,board,candidate['revision'])
        reference={'experiment_id':'opamp-connectivity','version':'1','approval':'approved','circuit':{'components':[
            {'id':'U1','type':'OPAMP','gain':100000,'pins':{p:'n'+str(i) for i,p in enumerate(candidate['components'][0]['pins'],1)}}]},'ports':{},'analysis':{'engine':'connectivity'}}
        request={'schema_version':'2.0','reference':reference,'input':{'adapter':'ml1','payload':{'candidate':candidate,'board':board}},
            'component_map':{'X1':'U1'},'safety_profile':'instructor_approved_low_voltage'}
        result=diagnose_input(request)
        self.assertEqual(result['status'],'needs_confirmation')
        self.assertIn('properties:X1',result['pending'])
        result,frameboard=fixture();capture=normalize_video(result,frameboard)
        candidate['image_sha256']=capture.image['sha256']
        capture.board=board;capture.candidate=candidate
        evaluated=capture.diagnose(reference,{'X1':'U1'},model_settings={'X1':{'gain':100000}},safety_profile='instructor_approved_low_voltage')
        self.assertEqual(evaluated['status'],'evaluated')
        self.assertTrue(any('ideal-model assumption' in x for x in evaluated['limitations']))
        with self.assertRaisesRegex(MediaError,'inconsistent_ideal_model'):
            capture.request(reference,{'X1':'U1'},model_settings={'X1':{'gain':1000}})
