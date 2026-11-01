import importlib.util
import unittest

from labvision.vlm_training import parse_points, target_json


class VLMTargetTests(unittest.TestCase):
    def test_coordinate_roundtrip_uses_pixel_centers(self):
        text = target_json([{'xy':[0,0]}, {'xy':[99,49]}],100,50)
        self.assertEqual(parse_points(text,100,50),[[0,0],[99,49]])

    def test_hidden_out_of_frame_is_not_a_visible_target(self):
        with self.assertRaises(ValueError):
            target_json([{'xy':[-1,5]}],100,50)

    def test_hallucinated_or_invalid_fields_are_rejected(self):
        for text in ['{"points":[[true,4]]}', '{"points":[[1001,0]]}',
                     '{"points":[],"confirmed":true}', '{"points":[[NaN,5]]}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_points(text,100,50)

    @unittest.skipUnless(importlib.util.find_spec('torch'),'Optional PyTorch not installed')
    def test_prompt_and_image_tokens_never_become_supervised_answers(self):
        import torch
        from labvision.vlm_training import answer_labels
        full = torch.tensor([[10,11,12,20,21]])
        labels = answer_labels(full,torch.tensor([[10,11,12]]))
        self.assertEqual(labels.tolist(),[[-100,-100,-100,20,21]])
        with self.assertRaises(ValueError):
            answer_labels(full,torch.tensor([[10,99,12]]))
