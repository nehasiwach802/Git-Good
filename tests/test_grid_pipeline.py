"""Image/board/revision guards for the ML1 automatic-grid -> ML2 boundary."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image
from test_autocalibration import fixture
from labvision.autocalibration import detect_grid
from labvision.geometry import calibration_quality
from reasoning.grid import normalize_grid, GridError
from reasoning.media import process_image, process_video, restore_capture, MediaError

ACK='reviewed_grid_alignment_and_printed_labels'


class GridPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data,cls.board,_=fixture()
        cls.proposal=detect_grid(cls.data,cls.board)
        assert cls.proposal['status']=='needs_orientation_review'
        rgb=np.asarray(Image.open(BytesIO(cls.data)).convert('RGB'))
        height,width=rgb.shape[:2]
        with TemporaryDirectory() as directory:
            path=Path(directory)/'grid.mp4'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(width,height))
            assert writer.isOpened()
            for _ in range(12):writer.write(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
            writer.release();cls.video=path.read_bytes()

    def capture(self):
        with patch.dict('os.environ',{'LABVISION_ENDPOINT_WEIGHTS':''}):
            capture=process_image(self.data,self.board,known_parts=['7400'])
        capture.frames[0]['grid_proposal']=normalize_grid(self.proposal,self.board,capture.image)
        return capture

    def accept(self,capture):
        return capture.accept_grid(capture.candidate['revision'],image_sha256=capture.image['sha256'],
            left_top='A30',right_top='F1',acknowledgement=ACK)

    def test_normalizes_geometry_without_fabricating_human_review(self):
        capture=self.capture();raw=deepcopy(self.proposal)
        raw.update(labels_confirmed=True,reviewed=True,private_path='/private')
        raw['calibration'].update(checks=[{'fake':'check'}],anchors=[{'fake':'anchor'}],image_to_board=[[0]*3]*3)
        value=normalize_grid(raw,self.board,capture.image)
        self.assertEqual(value['status'],'needs_orientation_review')
        self.assertFalse(value['reviewed']);self.assertFalse(value['labels_confirmed'])
        self.assertNotIn('private_path',value)
        self.assertEqual(value['calibration']['checks'],[])
        self.assertFalse(calibration_quality(value['calibration'],self.board)['validated'])
        self.assertEqual(normalize_grid(value,self.board,capture.image),value)

    def test_bad_geometry_or_binding_fails_to_manual_fallback(self):
        capture=self.capture()
        mutations=[lambda p:p.update(image_sha256='0'*64),lambda p:p.update(board_fingerprint='0'*64),
            lambda p:p.update(image_size=[1,1]),lambda p:p['holes'].update(A1=[-1,0]),
            lambda p:p['holes'].update(A1=[True,0]),lambda p:p['holes'].update(A1=[float('nan'),0]),
            lambda p:p['calibration'].update(board_to_image=[[0]*3]*3),
            lambda p:p['quality'].update(holdout_count=True),lambda p:p['quality'].update(matched_fraction=.1),
            lambda p:p['quality'].update(holdout_p90_error_pitch=float('inf')),
            lambda p:p['holes'].pop('A1')]
        for mutate in mutations:
            p=deepcopy(self.proposal);mutate(p)
            with self.subTest(mutation=mutate):
                self.assertEqual(normalize_grid(p,self.board,capture.image)['status'],'unavailable')
        self.assertIsNone(normalize_grid(None,self.board,capture.image))

    def test_acceptance_maps_independent_strip_directions_without_confirming(self):
        original=self.capture();xy=self.proposal['holes']['E5']
        preview=original.suggest_hole(1,image_sha256=original.image['sha256'],xy=xy)
        self.assertEqual(preview['provisional_hole'],'E5');self.assertIsNone(preview['hole'])
        capture=self.accept(original)
        self.assertEqual(original.candidate['revision'],1)
        self.assertEqual(capture.candidate['revision'],2)
        result=capture.suggest_hole(2,image_sha256=capture.image['sha256'],xy=xy)
        self.assertEqual(result['hole'],'E26');self.assertFalse(result['confirmed'])
        self.assertIsNone(capture.candidate['reviewed_revision']);self.assertFalse(capture.candidate['board_confirmed'])
        self.assertIsNone(capture.calibration)
        self.assertFalse(capture.grid_proposal['labels_confirmed'])
        a,b=self.proposal['holes']['A10'],self.proposal['holes']['B10']
        midpoint=[(x+y)/2 for x,y in zip(a,b)]
        result=capture.suggest_hole(2,image_sha256=capture.image['sha256'],xy=midpoint)
        self.assertIsNone(result['hole']);self.assertFalse(result['confirmed'])
        self.assertEqual(set(result['alternatives']),{'A21','B21'})

    def test_acceptance_and_touch_guard_stale_revisions_pixels_and_labels(self):
        capture=self.capture();kwargs=dict(image_sha256=capture.image['sha256'],left_top='A30',right_top='F1',acknowledgement=ACK)
        for revision,changes in [(True,{}),(0,{}),(1,{'image_sha256':'0'*64}),
                                  (1,{'acknowledgement':''}),(1,{'left_top':'A2'}),(1,{'right_top':'E30'})]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                capture.accept_grid(revision,**{**kwargs,**changes})
        capture=self.accept(capture)
        for xy in ([float('nan'),0],[-1,1],[True,1],[capture.image['width'],0],[1e300,0]):
            with self.assertRaises(GridError):capture.suggest_hole(2,image_sha256=capture.image['sha256'],xy=xy)
        with self.assertRaises(MediaError):capture.suggest_hole(1,image_sha256=capture.image['sha256'],xy=[1,1])

    def test_restore_acceptance_and_changed_proposal_rejection(self):
        capture=self.accept(self.capture())
        assets={capture.image['sha256']:capture.image_bytes}
        state=json.loads(json.dumps(capture.snapshot(),allow_nan=False))
        restored=restore_capture(state,assets.__getitem__)
        self.assertEqual(restored.snapshot(),state)
        point=restored.suggest_hole(2,image_sha256=restored.image['sha256'],xy=self.proposal['holes']['F5'])
        self.assertEqual(point['hole'],'F5')
        bad=deepcopy(state);bad['media']['grid_review']['image_sha256']='0'*64
        with self.assertRaises(GridError):restore_capture(bad,assets.__getitem__)
        bad=deepcopy(state);bad['media']['frames'][0]['grid_proposal']['holes']['A1'][0]+=1
        with self.assertRaises(GridError):restore_capture(bad,assets.__getitem__)
        updated=capture.apply_to_record({'measurements':[{'old':1}],'diagnostic':{'old':1}})
        self.assertEqual(updated['measurements'],[]);self.assertIsNone(updated['diagnostic'])

    def test_frame_change_clears_label_acceptance(self):
        capture=self.accept(self.capture())
        stream=BytesIO();Image.new('RGB',(16,12),'white').save(stream,format='JPEG')
        with patch.dict('os.environ',{'LABVISION_ENDPOINT_WEIGHTS':''}):
            other=process_image(stream.getvalue(),self.board,known_parts=['7400'])
        other.frames[0]['id']='F2';capture.frames+=other.frames
        capture._bytes['F2']=other.image_bytes
        with patch.dict('os.environ',{'LABVISION_ENDPOINT_WEIGHTS':''}):changed=capture.select_frame('F2')
        self.assertNotIn('grid_review',changed.media);self.assertIsNone(changed.grid_proposal)
        with self.assertRaises(GridError):changed.suggest_hole(3,image_sha256=changed.image['sha256'],xy=[1,1])

    def test_grid_review_does_not_change_ml3_diagnostic_contract(self):
        from reasoning.api import diagnose_input
        from labvision.handoff import reasoning_input
        capture=self.accept(self.capture())
        candidate=json.loads(Path('examples/7400-not.candidate.json').read_text())
        candidate.update(candidate_id=capture.candidate['candidate_id'],revision=capture.candidate['revision'],
                         image_sha256=capture.image['sha256'])
        capture.candidate=candidate
        capture.confirm(2,acknowledgement='reviewed_all_connections_and_board')
        reference=json.loads(Path('examples/generalized/ml1-7400.json').read_text())['reference']
        context={'safety_profile':'instructor_approved_low_voltage','measurements':[], 'student_expectations':[]}
        expected=diagnose_input({'schema_version':'2.0','reference':reference,'component_map':{'U1':'U1'},
            'input':reasoning_input(capture.candidate,capture.board),**context})
        self.assertEqual(capture.diagnose(reference,{'U1':'U1'},**context),expected)

    def test_real_video_subprocess_carries_validated_grid_metadata(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'grid.mp4'
            path.write_bytes(self.video)
            with patch.dict('os.environ',{'LABVISION_ENDPOINT_WEIGHTS':''}):
                capture=process_video(path,self.board,known_parts=['7400'],auto_grid=True,deadline_s=30)
            self.assertEqual(capture.grid_proposal['status'],'needs_orientation_review')
            self.assertEqual(capture.media['selection'],'sharpest_grid_proposal')
            self.assertIsNone(capture.candidate['reviewed_revision'])
            self.assertNotIn('jpeg_bytes',json.dumps(capture.snapshot()))
            self.assertEqual(capture.grid_proposal['image_sha256'],capture.image['sha256'])
            for value in (1,None,'true'):
                with self.assertRaisesRegex(MediaError,'invalid_auto_grid_flag'):
                    process_video(path,self.board,auto_grid=value)


