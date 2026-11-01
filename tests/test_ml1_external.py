import json
from pathlib import Path
import tempfile
import unittest

from labvision.annotation import (new_session, set_calibration, set_external_terminal,
                                 training_record, annotate, set_rail_groups)
from labvision.core import CandidateError, compile_netlist, confirm, correct, pending, validate
from labvision.geometry import hole_positions, project, calibrate, calibration_quality


ROOT = Path(__file__).resolve().parents[1]


class ExternalTerminalTests(unittest.TestCase):
    def setUp(self):
        self.board = json.loads((ROOT/'examples/board-30.json').read_text())
        self.candidate = json.loads((ROOT/'examples/7400-not.candidate.json').read_text())
        self.candidate['schema_version'] = '0.2'

    def terminal(self, identifier):
        return {'hole': None, 'external_terminal': identifier, 'alternatives': [],
                'source': 'manual', 'confidence': 'likely', 'confirmed': False,
                'reason': 'Test external terminal'}

    def test_external_wire_and_supply_port_merge_without_a_fake_hole(self):
        # Connect a logical VCC tap to the external end of an actual supply wire.
        vcc = next(p for p in self.candidate['ports'] if p['role'] == 'vcc')
        self.candidate['wires'].append({'id': 'SupplyLead',
            'a': self.terminal('CLIP_A'),
            'b': dict(vcc['endpoint'], hole='G10')})
        vcc['endpoint'] = self.terminal('CLIP_A')
        net = compile_netlist(confirm(self.candidate, self.board, 1), self.board)
        port = next(p for p in net['ports'] if p['role'] == 'vcc')
        self.assertEqual(net['external_terminals']['CLIP_A'], port['node'])
        self.assertIn('G10', net['nodes'][port['node']])
        self.assertFalse(any('CLIP_A' in holes for holes in net['nodes'].values()))
        self.assertEqual(net['schema_version'], '0.2')
        from labvision.digital import check_not
        self.assertTrue(check_not(net)['topology_matches'])

    def test_distinct_external_terminals_do_not_merge(self):
        for port in self.candidate['ports']:
            if port['role'] in ('vcc', 'gnd'):
                port['endpoint'] = self.terminal(port['role'].upper())
        net = compile_netlist(confirm(self.candidate, self.board, 1), self.board)
        self.assertNotEqual(net['external_terminals']['VCC'], net['external_terminals']['GND'])

    def test_v01_cannot_silently_carry_external_semantics(self):
        self.candidate['schema_version'] = '0.1'
        self.candidate['ports'][0]['endpoint'] = self.terminal('CLIP')
        with self.assertRaises(CandidateError):
            validate(self.candidate, self.board)

    def test_external_and_hole_cannot_both_be_set_and_unknown_still_blocks(self):
        p = self.candidate['ports'][0]['endpoint']
        p['external_terminal'] = 'CLIP'
        with self.assertRaises(CandidateError):
            validate(self.candidate, self.board)
        self.candidate['ports'][0]['endpoint'] = self.terminal('CLIP')
        self.candidate['ports'][0]['endpoint']['external_terminal'] = None
        self.assertTrue(any('unknown' in text for text in pending(self.candidate, self.board)))
        with self.assertRaises(CandidateError):
            confirm(self.candidate, self.board, 1)

    def test_board_correction_removes_external_assignment(self):
        self.candidate['ports'][0]['endpoint'] = self.terminal('CLIP')
        revised = correct(self.candidate, self.board, self.candidate['ports'][0]['id'], 'A20', 1)
        self.assertIsNone(revised['ports'][0]['endpoint'].get('external_terminal'))

    def test_pixel_click_preserved_without_projection_and_review_invalidated(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/'image.bin'
            image.write_bytes(b'identity')
            session = new_session(image, [600, 800], self.board, 'test', self.candidate)
            positions = hole_positions(self.board)
            transform = [[20, 0, 100], [0, 20, 100], [0, 0, 1]]
            anchors = [{'hole': h, 'xy': project(transform, positions[h])}
                       for h in ('A1', 'J1', 'J30', 'A30')]
            checks = [{'hole': h, 'xy': project(transform, positions[h])} for h in ('A15', 'J15')]
            set_calibration(session, anchors, checks)
            target = session['candidate']['wires'][0]['id']+'.a'
            annotate(session, target, [550, 750])
            session['candidate']['wires'][0]['pairing_reviewed'] = True
            set_external_terminal(session, target, 'CLIP_BOTTOM')
            p = session['candidate']['wires'][0]['a']
            self.assertEqual(p['image_xy'], [550, 750])
            self.assertEqual(p['external_terminal'], 'CLIP_BOTTOM')
            self.assertIsNone(p['hole'])
            self.assertFalse(session['candidate']['wires'][0]['pairing_reviewed'])
            labels = training_record(session, reviewed=True)
            self.assertEqual(labels['label_version'], '0.2')
            self.assertEqual(labels['wires'][0]['a']['endpoint_kind'], 'external')
            self.assertEqual(labels['wires'][0]['a']['external_terminal'], 'CLIP_BOTTOM')
            set_calibration(session, anchors, checks)
            self.assertEqual(p['external_terminal'], 'CLIP_BOTTOM')
            annotate(session, target, project(transform, positions['A20']))
            self.assertIsNone(p.get('external_terminal'))

    def test_split_rail_groups_require_review_and_cannot_merge_strip_holes(self):
        from labvision.core import make_board, board_groups
        board = make_board(10)
        positions = hole_positions(board)
        for name, xy in [('R1', [-3, 1]), ('R2', [-3, 3]), ('R3', [-3, 6]), ('R4', [-3, 8])]:
            positions[name] = xy
            board['groups'].append([name])
        board['hole_positions'] = positions
        board['unverified_rail_holes'] = ['R1', 'R2', 'R3', 'R4']
        anchors = [{'hole': h, 'xy': positions[h]} for h in ('A1', 'J1', 'J10', 'A10')]
        checks = [{'hole': h, 'xy': positions[h]} for h in ('A5', 'J5')]
        session = {'board': board, 'calibration': calibrate(board, anchors, checks),
                   'candidate': {'revision': 1, 'board_confirmed': True, 'reviewed_revision': 1}}
        with self.assertRaises(CandidateError):
            set_rail_groups(session, [['R1', 'R2', 'A1'], ['R3', 'R4']], reviewed=True)
        set_rail_groups(session, [['R1', 'R2'], ['R3', 'R4']])
        self.assertTrue(session['board']['unverified_rail_holes'])
        set_rail_groups(session, [['R1', 'R2'], ['R3', 'R4']], reviewed=True)
        groups = board_groups(session['board'])
        self.assertEqual(groups['R1'], groups['R2'])
        self.assertNotEqual(groups['R1'], groups['R3'])
        self.assertFalse(session['board']['unverified_rail_holes'])
        self.assertFalse(session['candidate']['board_confirmed'])
        self.assertTrue(calibration_quality(session['calibration'], session['board'])['validated'])


if __name__ == '__main__':
    unittest.main()
