import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from labvision.core import CandidateError, make_board
from labvision.detection import EndpointDetector
from labvision.detector_review import import_predictions
from labvision.annotation import new_session
from labvision.upload import extract_upload


class UploadDetectorTests(unittest.TestCase):
    def setUp(self):
        stream = io.BytesIO()
        Image.new('RGB', (100,100)).save(stream, format='PNG')
        self.data = stream.getvalue()
        self.board = make_board(10)

    def detector(self, weights):
        model = Mock()
        boxes = Mock()
        boxes.xyxy.cpu.return_value.tolist.return_value = [[10.,20.,30.,40.]]
        boxes.conf.cpu.return_value.tolist.return_value = [.8]
        model.predict.return_value = [Mock(boxes=boxes)]
        return EndpointDetector(weights, model_factory=lambda path: model)

    def test_upload_proposals_are_image_bound_and_do_not_invent_wires(self):
        with tempfile.TemporaryDirectory() as folder:
            weights = Path(folder)/'trusted.pt'
            weights.write_bytes(b'mock weights')
            detector = self.detector(weights)
            result = extract_upload(self.data, self.board, known_parts=['7400'],
                                    try_vision=False, detector=detector)
            self.assertEqual(result['mode'], 'manual')
            self.assertEqual(result['candidate']['wires'], [])
            self.assertIsNone(result['netlist'])
            detection = result['endpoint_detection']
            point = detection['videos'][0]['frames'][0]['proposals'][0]
            self.assertFalse(point['confirmed'])
            self.assertIsNone(point['hole'])
            image = Path(folder)/'image.png'
            image.write_bytes(self.data)
            session = new_session(image, [100,100], self.board, 'test')
            self.assertEqual(import_predictions(session, detection), 1)
            self.assertEqual(import_predictions(session, result), 1)

    def test_detector_failure_keeps_manual_entry_available(self):
        result = extract_upload(self.data, self.board, try_vision=False,
                                detector=Mock(side_effect=RuntimeError('PRIVATE PATH')))
        self.assertEqual(result['endpoint_detection']['status'], 'unavailable')
        self.assertEqual(result['mode'], 'manual')
        self.assertNotIn('PRIVATE PATH', json.dumps(result))

    def test_invalid_upload_never_calls_detector(self):
        detector = Mock()
        with self.assertRaises(CandidateError):
            extract_upload(b'bad', self.board, detector=detector)
        detector.assert_not_called()

    def test_unconfigured_has_no_optional_model_import(self):
        with patch.dict('os.environ', {'LABVISION_ENDPOINT_WEIGHTS': ''}):
            result = extract_upload(self.data, self.board, try_vision=False)
        self.assertEqual(result['endpoint_detection']['status'], 'disabled')

    def test_detector_rejects_wrong_image_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            weights, image = Path(folder)/'weights.pt', Path(folder)/'image.png'
            weights.write_bytes(b'mock')
            image.write_bytes(self.data)
            detector = self.detector(weights)
            with self.assertRaises(CandidateError):
                detector(image, [100,100], 'wrong')
            detector.model.predict.assert_not_called()


if __name__ == '__main__':
    unittest.main()
