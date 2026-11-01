import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image
from labvision.core import CandidateError, make_board
from labvision.video_upload import process_video


class VideoUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'sample.avi'
        writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
        self.assertTrue(writer.isOpened())
        for i in range(16):
            image = np.full((240,320,3),220,dtype=np.uint8)
            cv2.line(image,(40+i,40),(180,180),(0,0,255),3)
            cv2.putText(image,str(i),(80,80),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
            writer.write(image)
        writer.release()
        self.board = make_board(30)

    def run_video(self, **kwargs):
        with patch.dict('os.environ', {'LABVISION_ENDPOINT_WEIGHTS':''}):
            return process_video(self.path,self.board,frame_count=3,samples=9,**kwargs)

    def test_bytes_survive_cleanup_and_selected_candidate_binds_to_returned_image(self):
        result = self.run_video(known_parts=['resistor'], max_edge=160)
        self.assertEqual(len(result['frames']),3)
        selected = next(f for f in result['frames'] if f['id']==result['selected_frame_id'])
        self.assertEqual(result['ml1']['candidate']['image_sha256'], selected['sha256'])
        self.assertEqual(result['ml1']['image']['sha256'],selected['sha256'])
        self.assertIsNone(result['ml1']['netlist'])
        self.assertIsNone(result['ml1']['candidate']['reviewed_revision'])
        self.assertEqual(result['ml1']['candidate']['wires'],[])
        self.assertEqual(result['video']['sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
        for f in result['frames']:
            self.assertEqual(hashlib.sha256(f['jpeg_bytes']).hexdigest(),f['sha256'])
            with Image.open(io.BytesIO(f['jpeg_bytes'])) as image:
                self.assertEqual(list(image.size),[f['width'],f['height']])
                self.assertLessEqual(max(image.size),160)
            self.assertEqual(f['endpoint_detection']['status'],'disabled')

    def test_detector_once_per_frame_and_provider_once_for_selected_only(self):
        def detect(path,size,sha):
            self.assertTrue(Path(path).exists())
            return {'status':'mock_proposals','image_sha256':sha}
        detector = Mock(side_effect=detect)
        provider = Mock(side_effect=CandidateError('unavailable'))
        result = self.run_video(detector=detector,extractor=provider,try_vision=True,selected_frame_id='F2')
        self.assertEqual(detector.call_count,3)
        provider.assert_called_once()
        self.assertEqual(result['selected_frame_id'],'F2')
        self.assertEqual(result['ml1']['mode'],'manual_fallback')
        self.assertEqual(result['ml1']['endpoint_detection'],result['frames'][1]['endpoint_detection'])
        self.assertEqual(result['ml1']['image']['sha256'],result['frames'][1]['sha256'])

    def test_failed_detector_does_not_lose_frames(self):
        result = self.run_video(detector=Mock(side_effect=RuntimeError('PRIVATE ERROR')))
        self.assertEqual(result['ml1']['endpoint_detection']['status'],'unavailable')
        self.assertEqual(len(result['frames']),3)
        self.assertNotIn('PRIVATE ERROR',str(result['limitations']))

    def test_auto_grid_selects_supported_frame_and_preserves_explicit_choice(self):
        reports = [{'status':'not_found'}, {'status':'needs_orientation_review'}, {'status':'not_found'}]
        with patch('labvision.autocalibration.detect_grid',side_effect=reports) as detect:
            result = self.run_video(auto_grid=True)
        self.assertEqual(detect.call_count,3)
        self.assertEqual(result['selected_frame_id'],'F2')
        self.assertEqual(result['selection'],'sharpest_grid_proposal')
        self.assertEqual(result['ml1']['grid_proposal'],reports[1])
        self.assertFalse(result['ml1']['candidate']['board_confirmed'])
        with patch('labvision.autocalibration.detect_grid',side_effect=reports):
            result = self.run_video(auto_grid=True,selected_frame_id='F1')
        self.assertEqual(result['selected_frame_id'],'F1')
        self.assertEqual(result['selection'],'explicit_frame_id')
        with patch('labvision.autocalibration.detect_grid',side_effect=CandidateError('unsupported')):
            result = self.run_video(auto_grid=True)
        self.assertEqual(result['selection'],'maximum_sampled_sharpness')
        self.assertEqual(result['ml1']['grid_proposal']['status'],'unavailable')

    def test_limits_and_invalid_selection_reject(self):
        for kwargs in ({'max_bytes':1},{'max_duration_s':.1},{'max_pixels':100},
                       {'selected_frame_id':'F99'},{'max_edge':0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(CandidateError):
                self.run_video(**kwargs)

    def test_invalid_video_rejects_before_models(self):
        self.path.write_bytes(b'not video')
        detector = Mock()
        with self.assertRaises(CandidateError):
            self.run_video(detector=detector)
        detector.assert_not_called()


if __name__ == '__main__':
    unittest.main()
