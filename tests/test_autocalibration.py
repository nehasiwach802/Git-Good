import hashlib
import io
import unittest

from PIL import Image, ImageDraw
from labvision.autocalibration import detect_grid, suggest_hole, label_mapping
from labvision.core import CandidateError, make_board
from labvision.geometry import hole_positions, project


def fixture(rows=30):
    board = make_board(rows)
    image = Image.new('RGB',(300,rows*14+85),'white')
    draw = ImageDraw.Draw(image)
    matrix = [[14, .035, 65],[0,14,40],[0,0,1]]
    for h,p in hole_positions(board).items():
        # A few occluded interior holes should not require manual grid anchors.
        if h in ('B12','C12','E15','F15','G15','H16'):
            continue
        x,y = project(matrix,p)
        draw.rectangle((x-2,y-2,x+2,y+2),fill='black')
    stream = io.BytesIO()
    image.save(stream,format='PNG')
    return stream.getvalue(),board,matrix


class AutoGridTests(unittest.TestCase):
    def test_known_grid_occlusion_and_touch_binding(self):
        data,board,matrix = fixture()
        result = detect_grid(data,board)
        self.assertEqual(result['status'],'needs_orientation_review')
        self.assertFalse(result['labels_confirmed'])
        self.assertEqual(len(result['holes']),300)
        # Independent rendering coordinates, not detector-derived expectations.
        for name in ('A1','J30','E15','F15'):
            truth = project(matrix,hole_positions(board)[name])
            self.assertLess(sum((a-b)**2 for a,b in zip(result['holes'][name],truth)),4)
        tap = suggest_hole(result,board,hashlib.sha256(data).hexdigest(),result['holes']['E15'])
        self.assertEqual(tap['provisional_hole'],'E15')
        self.assertIsNone(tap['hole'])
        self.assertFalse(tap['confirmed'])
        with self.assertRaises(CandidateError):
            suggest_hole(result,board,'different-frame',result['holes']['E15'])
        with self.assertRaises(CandidateError):
            suggest_hole(result,make_board(31),result['image_sha256'],[65,40])

    def test_blank_and_wrong_row_count_rejected(self):
        data,board,_ = fixture()
        self.assertEqual(detect_grid(data,make_board(63))['status'],'not_found')
        stream = io.BytesIO()
        Image.new('RGB',(300,500),'white').save(stream,format='PNG')
        self.assertEqual(detect_grid(stream.getvalue(),board)['status'],'not_found')

    def test_ambiguous_touch_stays_unknown_and_no_review_granted(self):
        data,board,_ = fixture()
        result = detect_grid(data,board)
        a,b = result['holes']['A10'],result['holes']['B10']
        tap = suggest_hole(result,board,result['image_sha256'],[(a[0]+b[0])/2,(a[1]+b[1])/2])
        self.assertIsNone(tap['provisional_hole'])
        from labvision.geometry import calibration_quality
        self.assertFalse(calibration_quality(result['calibration'],board)['validated'])

    def test_reject_rail_profile_and_oversize_bytes(self):
        data,board,_ = fixture()
        board['groups'].append(['RAIL1'])
        board['hole_positions'] = {**hole_positions(make_board(30)), 'RAIL1':[-3,0]}
        with self.assertRaises(CandidateError):
            detect_grid(data,board)
        with self.assertRaises(CandidateError):
            detect_grid(b'x'*(5*1024*1024+1),make_board(30))

    def test_opposite_strip_numbering_and_mirrored_columns(self):
        data,board,_ = fixture()
        mapping = label_mapping(board,left_top='A30',right_top='F1')
        self.assertEqual(mapping['E5'],'E26')
        self.assertEqual(mapping['F5'],'F5')
        proposal = detect_grid(data,board)
        tap = suggest_hole(proposal,board,proposal['image_sha256'],proposal['holes']['E5'],verified_label_map=mapping)
        self.assertEqual(tap['hole'],'E26')
        self.assertFalse(tap['confirmed'])
        reversed_map = label_mapping(board,left_top='J1',right_top='E30')
        self.assertEqual(reversed_map['A1'],'J1')
        self.assertEqual(reversed_map['J30'],'A1')
        for left,right in [('A2','F1'),('A30','E30'),('A0','F1')]:
            with self.assertRaises(CandidateError):
                label_mapping(board,left_top=left,right_top=right)
