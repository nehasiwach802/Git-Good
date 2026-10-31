from copy import deepcopy
import json
from pathlib import Path
import unittest

from labvision.core import CandidateError, confirm, compile_netlist, endpoints
from labvision.dataset import labels_from_reviewed_export
from labvision.geometry import calibrate, hole_positions, project


ROOT = Path(__file__).resolve().parents[1]


class ReviewedDatasetTests(unittest.TestCase):
    def setUp(self):
        board = json.loads((ROOT/'examples/board-30.json').read_text())
        candidate = json.loads((ROOT/'examples/7400-not.candidate.json').read_text())
        positions = hole_positions(board)
        transform = [[20, 0, 50], [0, 20, 50], [0, 0, 1]]
        for _, p, _ in endpoints(candidate):
            p.update(source='vision', visible=True, image_xy=project(transform, positions[p['hole']]))
        # A pose-derived IC pin must not become a visible label after acceptance.
        candidate['components'][0]['pins']['1']['visible'] = None
        calibration = calibrate(board,
            [{'hole': h, 'xy': project(transform, positions[h])} for h in ('A1', 'J1', 'J30', 'A30')],
            [{'hole': h, 'xy': project(transform, positions[h])} for h in ('A15', 'J15')])
        self.session = {'board': board, 'candidate': candidate, 'calibration': calibration,
                        'image_sha256': 'test', 'image_name': 'fixture.jpg', 'image_size': [500, 700],
                        'image_type': 'real', 'assembly_id': 'fixture-only'}
        self.netlist = compile_netlist(confirm(candidate, board, 1), board)

    def test_matching_review_accepts_visible_proposals_without_inventing_hidden_pixels(self):
        before = deepcopy(self.session)
        labels = labels_from_reviewed_export(self.session, self.netlist)
        self.assertEqual(self.session, before)
        self.assertEqual(labels['wires'][0]['a']['label_status'], 'annotated')
        self.assertIsNone(labels['components'][0]['pins']['1']['visible'])
        self.assertTrue(labels['wires'][0]['pairing_reviewed'])
        self.assertEqual(labels['review_evidence']['original_endpoint_sources']['W1.a'], 'vision')

    def test_changed_pixel_cannot_inherit_an_older_review(self):
        self.session['candidate']['wires'][0]['a']['image_xy'][0] += 1
        with self.assertRaises(CandidateError):
            labels_from_reviewed_export(self.session, self.netlist)

    def test_missing_or_different_review_is_rejected(self):
        self.netlist['revision'] += 1
        with self.assertRaises(CandidateError):
            labels_from_reviewed_export(self.session, self.netlist)
        self.netlist['revision'] -= 1
        self.netlist['status'] = 'unreviewed'
        with self.assertRaises(CandidateError):
            labels_from_reviewed_export(self.session, self.netlist)


if __name__ == '__main__':
    unittest.main()
