import json
from pathlib import Path
import tempfile
import unittest

from tools.review_endpoint_seeds import load_review, save_review


class ReviewPersistenceTests(unittest.TestCase):
    def test_resume_preserves_corrections_without_changing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / 'seed.json'
            output = Path(directory) / 'review.json'
            original = {'frames': [{'video_id': 'v1', 'image': 'frame.jpg',
                                   'image_sha256': 'abc', 'xy': [[1, 2]], 'reviewed': False}]}
            seed.write_text(json.dumps(original), encoding='utf-8')
            data = load_review(seed, output)
            data['frames'][0].update(xy=[[3, 4]], reviewed=True)
            save_review(data, output)
            resumed = load_review(seed, output)
            self.assertEqual(resumed['frames'][0]['xy'], [[3, 4]])
            self.assertTrue(resumed['human_reviewed'])
            self.assertEqual(json.loads(seed.read_text()), original)
            self.assertFalse(output.with_suffix('.json.tmp').exists())
            resumed['frames'][0]['reviewed'] = False
            save_review(resumed, output)
            self.assertFalse(load_review(seed, output)['human_reviewed'])

    def test_refuses_mismatched_saved_review(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / 'seed.json'
            output = Path(directory) / 'review.json'
            data = {'frames': [{'video_id': 'v1', 'image': 'frame.jpg', 'image_sha256': 'abc'}]}
            seed.write_text(json.dumps(data), encoding='utf-8')
            data['frames'][0]['image_sha256'] = 'different'
            output.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'different seeds'):
                load_review(seed, output)


if __name__ == '__main__':
    unittest.main()
