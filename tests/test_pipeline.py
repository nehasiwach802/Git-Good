import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
import tempfile

from labvision.core import (CandidateError, board_groups, compile_netlist, confirm,
                            correct, endpoint, endpoints, make_board, pending, validate)
from labvision.digital import check_not
from labvision.vision import extract, normalize, parse_response
from labvision.review import review_markdown


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.board = load("board-30.json")
        self.candidate = load("7400-not.candidate.json")

    def reviewed(self):
        return confirm(self.candidate, self.board, 1)

    def test_unreviewed_export_is_blocked(self):
        self.assertTrue(pending(self.candidate, self.board))
        with self.assertRaises(CandidateError):
            compile_netlist(self.candidate, self.board)

    def test_breadboard_center_gap_and_rows_remain_separate(self):
        groups = board_groups(self.board)
        self.assertEqual(groups["A10"], groups["E10"])
        self.assertNotEqual(groups["E10"], groups["F10"])
        self.assertNotEqual(groups["A10"], groups["A11"])

    def test_wires_merge_but_chip_pins_do_not(self):
        net = compile_netlist(self.reviewed(), self.board)
        pins = net["components"][0]["pins"]
        self.assertEqual(pins["1"], pins["2"])
        self.assertNotEqual(pins["1"], pins["3"])
        self.assertNotEqual(pins["7"], pins["14"])

    def test_reference_truth_table(self):
        result = check_not(compile_netlist(self.reviewed(), self.board))
        self.assertTrue(result["topology_matches"])
        self.assertFalse(result["warnings"])
        self.assertEqual(result["truth_table"], [
            {"input": 0, "expected_output": 1}, {"input": 1, "expected_output": 0}])

    def test_wrong_wiring_survives_export_and_fails_reference(self):
        wrong = correct(self.reviewed(), self.board, "W1.b", "A17", 1)
        wrong = confirm(wrong, self.board, 2)
        net = compile_netlist(wrong, self.board)
        self.assertNotEqual(net["components"][0]["pins"]["1"],
                            net["components"][0]["pins"]["2"])
        self.assertFalse(check_not(net)["topology_matches"])

    def test_revision_and_review_invalidated_by_correction(self):
        revised = correct(self.reviewed(), self.board, "W1.b", "A17", 1)
        self.assertEqual(revised["revision"], 2)
        self.assertIsNone(revised["reviewed_revision"])
        with self.assertRaises(CandidateError):
            compile_netlist(revised, self.board)
        with self.assertRaises(CandidateError):
            confirm(revised, self.board, 1)

    def test_unknown_and_alternative_holes_block_confirmation(self):
        point = self.candidate["components"][0]["pins"]["1"]
        point["hole"] = None
        with self.assertRaises(CandidateError):
            confirm(self.candidate, self.board, 1)
        point["hole"] = "E10"
        point["alternatives"] = ["E9"]
        with self.assertRaises(CandidateError):
            confirm(self.candidate, self.board, 1)

    def test_invalid_holes_and_duplicate_occupancy(self):
        self.candidate["wires"][0]["a"]["hole"] = "Z99"
        with self.assertRaises(CandidateError):
            validate(self.candidate, self.board)
        self.candidate["wires"][0]["a"]["hole"] = "E10"
        with self.assertRaises(CandidateError):
            validate(self.candidate, self.board)

    def test_rails_connect_only_as_profile_declares(self):
        board = make_board(2)
        board["groups"] += [["L+1", "L+2"], ["L+3", "L+4"]]
        groups = board_groups(board)
        self.assertEqual(groups["L+1"], groups["L+2"])
        self.assertNotEqual(groups["L+1"], groups["L+3"])

    def test_passive_component_does_not_short_its_nodes(self):
        candidate = self.reviewed()
        candidate["components"].append({"id": "R1", "part": "resistor", "value_si": 1000,
            "value_confirmed": True, "identity_confirmed": True,
            "pins": {"1": dict(endpoint("C10"), confirmed=True),
                     "2": dict(endpoint("C12"), confirmed=True)}})
        net = compile_netlist(candidate, self.board)
        self.assertNotEqual(net["components"][1]["pins"]["1"], net["components"][1]["pins"]["2"])
        self.assertFalse(check_not(net)["topology_matches"])

    def test_supply_short_is_observed_but_not_certified(self):
        candidate = self.reviewed()
        candidate["wires"].append({"id": "Wshort",
            "a": dict(endpoint("H10"), confirmed=True),
            "b": dict(endpoint("C14"), confirmed=True)})
        result = check_not(compile_netlist(candidate, self.board))
        self.assertFalse(result["topology_matches"])

    def test_vision_cannot_self_confirm(self):
        raw = copy.deepcopy(self.candidate)
        for component in raw["components"]:
            component["pins"] = [{"pin": pin, "endpoint": p} for pin, p in component["pins"].items()]
        candidate = normalize(raw, self.board)
        self.assertFalse(candidate["board_confirmed"])
        self.assertIsNone(candidate["reviewed_revision"])
        self.assertFalse(candidate["components"][0]["identity_confirmed"])
        self.assertTrue(all(not p["confirmed"] for p in candidate["components"][0]["pins"].values()))
        with self.assertRaises(CandidateError):
            compile_netlist(candidate, self.board)

    def test_compact_vision_endpoints_receive_unreviewed_defaults(self):
        raw = copy.deepcopy(self.candidate)
        for _, point, _ in endpoints(raw):
            point.pop("reason")
            point.pop("alternatives")
        for component in raw["components"]:
            component["pins"] = [{"pin": pin, "endpoint": p} for pin, p in component["pins"].items()]
        candidate = normalize(raw, self.board)
        for _, point, _ in endpoints(candidate):
            self.assertEqual(point["alternatives"], [])
            self.assertIsInstance(point["reason"], str)
            self.assertFalse(point["confirmed"])

    def test_provider_truncation_or_blocked_content_is_rejected(self):
        for response in ({}, [], {"candidates": [None]},
                         {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                         {"candidates": [{"finishReason": "STOP", "content": None}]}):
            with self.assertRaises(CandidateError):
                parse_response(response, self.board)

    def test_missing_key_fails_before_network(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch("labvision.config.load_dotenv", return_value={}), \
                patch("urllib.request.urlopen") as network:
            with self.assertRaisesRegex(CandidateError, "GEMINI_API_KEY"):
                extract("not-read.jpeg", self.board, "model-id")
            network.assert_not_called()

    def test_invalid_timeout_fails_before_network(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-test-key", "GEMINI_MODEL": "model-id"}), \
                patch("urllib.request.urlopen") as network:
            with self.assertRaisesRegex(CandidateError, "timeout"):
                extract("not-read.jpeg", self.board, timeout=301)
            network.assert_not_called()

    def test_review_sheet_exposes_unknowns_and_blocks_export(self):
        self.candidate["components"][0]["pins"]["1"]["hole"] = None
        report = review_markdown(self.candidate, self.board)
        self.assertIn("U1.1 | UNKNOWN", report)
        self.assertIn("BLOCKED", report)
        self.assertIn("not a labelled ground truth", report)

    def test_raw_response_saved_even_when_candidate_validation_fails(self):
        response = {"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps({"components": [], "wires": [], "ports": [], "issues": []})}]}}]}
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-test-key", "GEMINI_MODEL": "model-id"}), \
                patch("pathlib.Path.read_bytes", return_value=b"\xff\xd8\xfftest-fixture"), \
                patch("urllib.request.urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
            target = Path(directory) / "provider.json"
            with self.assertRaises(CandidateError):
                extract("fake.jpeg", self.board, raw_response_path=target)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), response)
            self.assertNotIn("dummy-test-key", target.read_text(encoding="utf-8"))

    def test_provider_timeout_preserves_manual_fallback(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-test-key", "GEMINI_MODEL": "model-id"}), \
                patch("pathlib.Path.read_bytes", return_value=b"\xff\xd8\xfftest-fixture"), \
                patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(CandidateError, "use manual entry"):
                extract("fake.jpeg", self.board, "model-id")

    def test_vision_round_trip_uses_header_and_requires_review(self):
        raw = copy.deepcopy(self.candidate)
        for component in raw["components"]:
            component["pins"] = [{"pin": pin, "endpoint": p} for pin, p in component["pins"].items()]
        response = {"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps(raw)}]}}]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-test-key", "GEMINI_MODEL": "model-id"}), \
                patch("pathlib.Path.read_bytes", return_value=b"\xff\xd8\xfftest-fixture"), \
                patch("urllib.request.urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = json.dumps(response).encode()
            result = extract("fake.jpeg", self.board, "model-id")
            request = network.call_args.args[0]
            self.assertNotIn("dummy-test-key", request.full_url)
            self.assertEqual(request.get_header("X-goog-api-key"), "dummy-test-key")
            self.assertFalse(result["board_confirmed"])
            self.assertEqual(len(result["image_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
