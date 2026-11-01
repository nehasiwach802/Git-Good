import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

try:
    import numpy as np
except ImportError:
    raise unittest.SkipTest("optional local vision tests require NumPy")
from PIL import Image, ImageDraw

from labvision.core import CandidateError, make_board
from labvision.geometry import calibrate, hole_positions, project
from labvision.localvision import thin, propose_red_wire_tips
from tools.run_local_baseline import compare_holes
from tools.predict_wire_pixels import main as pixel_main


class LocalVisionTests(unittest.TestCase):
    def setUp(self):
        self.board = make_board(10)
        self.positions = hole_positions(self.board)
        self.transform = [[20, 0, 100], [0, 20, 100], [0, 0, 1]]
        anchors = [{"hole": h, "xy": project(self.transform, self.positions[h])}
                   for h in ("A1", "J1", "J10", "A10")]
        checks = [{"hole": h, "xy": project(self.transform, self.positions[h])} for h in ("A5", "J5")]
        self.calibration = calibrate(self.board, anchors, checks)

    def test_red_line_endpoints_map_through_crop_to_native_holes(self):
        photo = Image.new("RGB", (400, 400), "white")
        draw = ImageDraw.Draw(photo)
        draw.line([tuple(project(self.transform, self.positions[h])) for h in ("A5", "D5")],
                  fill=(200, 10, 10), width=5)
        result = propose_red_wire_tips(photo, self.board, self.calibration, [50, 80, 350, 300])
        self.assertEqual({p["hole"] for p in result["proposals"]}, {"A5", "D5"})
        self.assertTrue(all(not p["confirmed"] and p["source"] == "vision" for p in result["proposals"]))
        self.assertTrue(all(p["tip_xy"][0] >= 95 for p in result["proposals"]))

    def test_blue_line_is_outside_declared_red_wire_scope(self):
        photo = Image.new("RGB", (400, 400), "white")
        ImageDraw.Draw(photo).line([(100, 180), (160, 180)], fill="blue", width=5)
        self.assertEqual(propose_red_wire_tips(photo, self.board, self.calibration)["proposals"], [])

    def test_thinning_does_not_wrap_image_edges(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[1:15, :3] = True
        mask[1:15, -3:] = True
        skeleton = thin(mask)
        self.assertTrue(skeleton[:, :3].any() and skeleton[:, -3:].any())
        self.assertFalse(skeleton[:, 3:-3].any())

    def test_evaluation_penalizes_duplicate_and_missed_proposals(self):
        result = compare_holes([{"hole": "A1"}]*3 + [{"hole": None}], ["A1", "A2"])
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["precision"], 1/3)
        self.assertEqual(result["recall"], 0.5)

    def test_network_failure_never_echoes_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"photo.jpg"
            Image.new("RGB", (20, 20), "white").save(image)
            output = Path(directory)/"run"
            secret = "FAKE_KEY_MUST_NOT_APPEAR"
            with patch("sys.argv", ["predict_wire_pixels", str(image), "--out", str(output)]), \
                 patch("tools.predict_wire_pixels.gemini_settings", return_value={"GEMINI_API_KEY": secret, "GEMINI_MODEL": "test-model"}), \
                 patch("urllib.request.urlopen", side_effect=urllib.error.URLError(secret)), \
                 contextlib.redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(pixel_main(), 1)
            self.assertNotIn(secret, captured.getvalue())
            self.assertNotIn(secret, (output/"metadata.json").read_text())

    def test_dry_run_never_reads_credentials_or_calls_network(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"photo.jpg"
            Image.new("RGB", (20, 20), "white").save(image)
            output = Path(directory)/"run"
            with patch("sys.argv", ["predict_wire_pixels", str(image), "--out", str(output), "--dry-run"]), \
                 patch("tools.predict_wire_pixels.gemini_settings") as settings, \
                 patch("urllib.request.urlopen") as network, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pixel_main(), 0)
            settings.assert_not_called()
            network.assert_not_called()
            self.assertFalse(json.loads((output/"metadata.json").read_text())["reference_labels_supplied"])


if __name__ == "__main__":
    unittest.main()
