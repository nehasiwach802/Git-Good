import unittest

from labvision.endpoint_training import audit_groups, region_box


class TrainingEvidenceTests(unittest.TestCase):
    def test_same_image_cannot_leak_by_renaming_video(self):
        with self.assertRaises(ValueError):
            audit_groups([{'sha256': 'identical', 'assembly_id': 'video-a', 'split': 'train'},
                          {'sha256': 'identical', 'assembly_id': 'video-b', 'split': 'test'}])

    def test_different_views_of_known_layout_cannot_leak(self):
        with self.assertRaises(ValueError):
            audit_groups([{'sha256': 'view-a', 'assembly_id': 'same-layout', 'split': 'train'},
                          {'sha256': 'view-b', 'assembly_id': 'same-layout', 'split': 'val'}])

    def test_unassigned_evidence_is_not_trainable(self):
        with self.assertRaises(ValueError):
            audit_groups([{'sha256': 'x', 'assembly_id': 'unknown', 'split': 'unassigned'}])

    def test_hidden_out_of_frame_endpoint_cannot_become_region(self):
        with self.assertRaises(ValueError):
            region_box([-1, 40], 100, 100)


if __name__ == '__main__':
    unittest.main()
