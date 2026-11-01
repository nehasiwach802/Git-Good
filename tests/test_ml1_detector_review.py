import copy
from pathlib import Path
import tempfile
import unittest

from labvision.annotation import new_session, add_wire, set_calibration
from labvision.core import CandidateError, make_board
from labvision.detector_review import import_predictions, assign_proposal


class DetectorReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        image = Path(self.temp.name)/'image.bin'
        image.write_bytes(b'bound image')
        self.session = new_session(image, [400, 400], make_board(10), 'test')
        add_wire(self.session, 'W1')
        set_calibration(self.session,
            [{'hole': h, 'xy': xy} for h, xy in [('A1', [100,100]),
             ('J1', [320,100]), ('J10', [320,280]), ('A10', [100,280])]],
            [{'hole': 'A5', 'xy': [100,180]}, {'hole': 'J5', 'xy': [320,180]}])
        self.frame = {'sha256': self.session['image_sha256'], 'image_size': [400,400],
                      'proposals': [{'id': 'P1', 'box': [96,136,104,144], 'confirmed': True}]}
        self.report = {'videos': [{'frames': [self.frame]}]}

    def test_import_does_not_change_wiring_and_assignment_is_unreviewed(self):
        before = copy.deepcopy(self.session['candidate'])
        import_predictions(self.session, self.report)
        self.assertEqual(before, self.session['candidate'])
        result = assign_proposal(self.session, 'W1.a', 'P1')
        self.assertEqual(result['hole'], 'A3')
        self.assertFalse(result['confirmed'])
        self.assertIsNone(result['visible'])
        self.assertFalse(self.session['candidate']['wires'][0]['pairing_reviewed'])
        self.assertIsNone(self.session['candidate']['reviewed_revision'])

    def test_wrong_image_and_bad_box_rejected_atomically(self):
        self.frame['sha256'] = 'other'
        with self.assertRaises(CandidateError):
            import_predictions(self.session, self.report)
        self.assertNotIn('detector_proposals', self.session)
        self.frame['sha256'] = self.session['image_sha256']
        self.frame['proposals'][0]['box'][0] = float('nan')
        with self.assertRaises(CandidateError):
            import_predictions(self.session, self.report)
        self.assertNotIn('detector_proposals', self.session)

    def test_requires_validated_calibration(self):
        import_predictions(self.session, self.report)
        self.session['calibration']['checks'] = []
        with self.assertRaises(CandidateError):
            assign_proposal(self.session, 'W1.a', 'P1')


if __name__ == '__main__':
    unittest.main()
