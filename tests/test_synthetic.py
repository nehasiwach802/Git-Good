import json
import math
from pathlib import Path
import tempfile
import unittest

from labvision.core import CandidateError
from labvision.geometry import calibrate, calibration_quality, project
from labvision.synthetic import generate, render


class SyntheticTests(unittest.TestCase):
    def test_render_has_exact_geometry_pairing_and_visibility(self):
        image, mask, labels, board = render(123, 456)
        self.assertEqual(image.size, tuple(labels["image_size"]))
        calibration = calibrate(board, labels["calibration_anchors"], labels["calibration_checks"])
        self.assertTrue(calibration_quality(calibration, board)["validated"])
        occupied = []
        for component in labels["components"]:
            occupied.extend(p["hole"] for p in component["pins"].values())
        for wire in labels["wires"]:
            self.assertLess(math.dist(wire["path_xy"][0], wire["a"]["xy"]), 1e-6)
            self.assertLess(math.dist(wire["path_xy"][-1], wire["b"]["xy"]), 1e-6)
            occupied += [wire[side]["hole"] for side in ("a", "b")]
            for side in ("a", "b"):
                p = wire[side]
                self.assertEqual(p["observable_hole"], p["hole"] if p["visible"] else None)
                if p["visible"]:
                    self.assertEqual(mask.getpixel(tuple(map(round, p["xy"]))), wire["mask_id"])
        self.assertEqual(len(occupied), len(set(occupied)))

    def test_seed_reproduces_images_and_labels(self):
        a, ma, la, _ = render("scene", "layout")
        b, mb, lb, _ = render("scene", "layout")
        self.assertEqual(a.tobytes(), b.tobytes())
        self.assertEqual(ma.tobytes(), mb.tobytes())
        self.assertEqual(la, lb)

    def test_variants_share_layout_and_split_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"dataset"
            result = generate(output, count=4, seed=7, variants=2)
            records = [json.loads(line) for line in (output/"manifest.jsonl").read_text().splitlines()]
            self.assertEqual(result["layouts"], 2)
            for assembly in {r["assembly_id"] for r in records}:
                self.assertEqual(len({r["split"] for r in records if r["assembly_id"] == assembly}), 1)
            a = json.loads((output/records[0]["labels"]).read_text())
            b = json.loads((output/records[1]["labels"]).read_text())
            self.assertEqual(a["electrical_groups"], b["electrical_groups"])
            self.assertNotEqual(a["hole_centers"], b["hole_centers"])
            with self.assertRaises(CandidateError):
                generate(output, count=1)


if __name__ == "__main__":
    unittest.main()
