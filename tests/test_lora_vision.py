import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional PyTorch not installed')
class LoRAFreezeTests(unittest.TestCase):
    def test_zero_initialized_adapter_preserves_pretrained_function(self):
        import torch
        from labvision.lora_vision import LoRALinear
        base = torch.nn.Linear(4, 3)
        x = torch.randn(2, 4)
        expected = base(x).detach()
        adapted = LoRALinear(base, rank=2, alpha=4)
        torch.testing.assert_close(adapted(x), expected)

    def test_adapter_can_learn_without_changing_frozen_weights(self):
        import torch
        from labvision.lora_vision import LoRALinear
        torch.manual_seed(7)
        adapted = LoRALinear(torch.nn.Linear(4, 3), rank=2, alpha=4, dropout=0)
        original = adapted.base.weight.detach().clone()
        optimizer = torch.optim.SGD([p for p in adapted.parameters() if p.requires_grad], lr=.1)
        adapted(torch.randn(2, 4)).sum().backward()
        self.assertIsNone(adapted.base.weight.grad)
        self.assertGreater(float(adapted.lora_B.weight.grad.abs().sum()), 0)
        optimizer.step()
        torch.testing.assert_close(adapted.base.weight, original)
        self.assertGreater(float(adapted.lora_B.weight.detach().abs().sum()), 0)

    def test_duplicate_predictions_do_not_count_as_multiple_true_positives(self):
        from labvision.lora_vision import region_metrics
        box = [1, 1, 5, 5]
        result = region_metrics([{'truth': [box], 'predictions':
                                  [{'box': box, 'score': .9}, {'box': box, 'score': .8}]}], .5)
        self.assertEqual((result['tp'], result['fp'], result['fn']), (1, 1, 0))
