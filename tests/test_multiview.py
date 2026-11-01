import unittest

import numpy as np

from labvision.multiview import consensus, register_view, warp_proposals, track_video_views


class MultiViewTests(unittest.TestCase):
    def test_votes_require_distinct_views(self):
        points = [{'xy': [100,100], 'score': .8, 'view': 'a'},
                  {'xy': [101,101], 'score': .7, 'view': 'a'}]
        self.assertEqual(consensus(points, [400,400], minimum_views=2), [])
        points.append({'xy': [102,100], 'score': .75, 'view': 'b'})
        result = consensus(points, [400,400], minimum_views=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['supporting_views'], ['a','b'])
        self.assertFalse(result[0]['confirmed'])
        self.assertIsNone(result[0]['hole'])

    def test_projection_and_out_of_frame(self):
        items = [{'box': [90,90,110,110], 'score': .8}]
        matrix = np.array([[1,0,20],[0,1,30],[0,0,1]], dtype=float)
        result = warp_proposals(items, matrix, [400,400], 'frame')
        self.assertEqual(result[0]['xy'], [120,130])
        self.assertEqual(warp_proposals(items, matrix, [50,50], 'frame'), [])

    def test_blank_registration_is_rejected(self):
        blank = np.zeros((200,200,3), dtype=np.uint8)
        matrix, diagnostic = register_view(blank, blank)
        self.assertIsNone(matrix)
        self.assertFalse(diagnostic['accepted'])

    def test_known_translation_recovers_planar_points(self):
        import cv2
        rng = np.random.default_rng(42)
        reference = rng.integers(0,256,(320,400,3),dtype=np.uint8)
        shift = np.float32([[1,0,12],[0,1,8]])
        source = cv2.warpAffine(reference, shift, (400,320))
        matrix, diagnostic = register_view(source, reference)
        self.assertTrue(diagnostic['accepted'])
        point = cv2.perspectiveTransform(np.float32([[[112,108]]]), matrix)[0,0]
        self.assertLess(np.linalg.norm(point-[100,100]), 1)

    def test_video_chain_translation(self):
        import cv2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'motion.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (320,240))
            self.assertTrue(writer.isOpened())
            image = np.random.default_rng(12).integers(0,256,(240,320,3),dtype=np.uint8)
            for i in range(9):
                writer.write(cv2.warpAffine(image,np.float32([[1,0,i],[0,1,0]]),(320,240)))
            writer.release()
            result = track_video_views(path, 0, [0,8], step=2)
            matrix, diagnostic = result[8]
            self.assertTrue(diagnostic['accepted'])
            point = cv2.perspectiveTransform(np.float32([[[108,100]]]),matrix)[0,0]
            self.assertLess(np.linalg.norm(point-[100,100]),1)


if __name__ == '__main__':
    unittest.main()
