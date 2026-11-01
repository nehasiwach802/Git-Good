import copy
import math
from pathlib import Path
import tempfile
import unittest

from labvision.annotation import (add_component, add_port, add_wire, annotate,
                                  candidate_from_session, new_session, set_calibration, verify_session)
from labvision.annotation import training_record
from labvision.core import CandidateError, compile_netlist, confirm, endpoints, make_board
from labvision.digital import check_not
import json
from labvision.geometry import (calibrate, calibration_quality, fit_homography,
                                hole_positions, inverse, project, snap)


class GeometryTests(unittest.TestCase):
    def test_outer_holes_preserve_grid_and_block_unverified_netlist(self):
        from labvision.annotation import add_outer_hole
        session = {"board": copy.deepcopy(self.board), "calibration": copy.deepcopy(self.calibration),
                   "candidate": {"revision": 1, "board_confirmed": True, "reviewed_revision": 1}}
        xy = project(self.mapping, [-4, 10])
        add_outer_hole(session, "R1", xy)
        self.assertTrue(calibration_quality(session["calibration"], session["board"])["validated"])
        self.assertEqual(snap(session["calibration"], session["board"], xy)["hole"], "R1")
        self.assertEqual(snap(session["calibration"], session["board"],
                              project(self.mapping, self.xy["D8"]))["hole"], "D8")
        with self.assertRaises(CandidateError):
            compile_netlist(session["candidate"], session["board"])
        with self.assertRaises(CandidateError):
            confirm(session["candidate"], session["board"], 2)

    def setUp(self):
        self.board = make_board(30)
        self.xy = hole_positions(self.board)
        self.mapping = [[22, 1.2, 120], [0.6, 18, 75], [0.0005, 0.001, 1]]
        self.anchors = [{"hole": h, "xy": project(self.mapping, self.xy[h])}
                        for h in ("A1", "J1", "J30", "A30")]
        self.checks = [{"hole": h, "xy": project(self.mapping, self.xy[h])} for h in ("A15", "J15")]
        self.calibration = calibrate(self.board, self.anchors, self.checks)

    def test_perspective_round_trip_and_grid_center(self):
        for h in ("A1", "D8", "F16", "J30"):
            xy = project(self.calibration["board_to_image"], self.xy[h])
            self.assertLess(math.dist(xy, project(self.mapping, self.xy[h])), 1e-7)
            self.assertEqual(snap(self.calibration, self.board, xy)["hole"], h)

    def test_midpoint_is_ambiguous_not_forced_to_a_hole(self):
        p = project(self.mapping, [0.5, 0])
        result = snap(self.calibration, self.board, p)
        self.assertIsNone(result["hole"])
        self.assertEqual(set(result["alternatives"]), {"A1", "B1"})

    def test_outside_board_is_unknown(self):
        self.assertIsNone(snap(self.calibration, self.board, project(self.mapping, [-10, -10]))["hole"])

    def test_degenerate_anchor_geometry_is_rejected(self):
        collinear = [{"hole": h, "xy": project(self.mapping, self.xy[h])} for h in ("A1", "A2", "A3", "A4")]
        with self.assertRaises(CandidateError):
            calibrate(self.board, collinear)

    def test_two_independent_checks_are_required(self):
        untested = calibrate(self.board, self.anchors)
        self.assertFalse(calibration_quality(untested, self.board)["validated"])
        wrong = copy.deepcopy(self.checks)
        wrong[0]["xy"][1] += 25
        self.assertFalse(calibration_quality(calibrate(self.board, self.anchors, wrong), self.board)["validated"])

    def test_board_change_invalidates_mapping(self):
        board = copy.deepcopy(self.board)
        board["id"] = "new-board"
        with self.assertRaises(CandidateError):
            snap(self.calibration, board, [100, 100])

    def test_nonstandard_rails_require_explicit_geometry(self):
        board = make_board(2)
        board["groups"].append(["L+1", "L+2"])
        with self.assertRaises(CandidateError):
            hole_positions(board)

    def test_partial_session_saves_hidden_points_and_blocks_candidate_export_without_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"image.bin"
            image.write_bytes(b"test-image-identity")
            session = new_session(image, [600, 700], self.board, "real-layout-1")
            add_component(session, "7400", "U1")
            set_calibration(session, self.anchors)
            annotate(session, "U1.1", visible=False)
            with self.assertRaises(CandidateError):
                candidate_from_session(session)
            session["calibration"] = self.calibration
            p = annotate(session, "U1.1", project(self.mapping, self.xy["E10"]))
            self.assertEqual(p["hole"], "E10")
            self.assertFalse(p["confirmed"])
            candidate = candidate_from_session(session)
            self.assertEqual(candidate["annotation_assembly_id"], "real-layout-1")
            image.write_bytes(b"another-image")
            with self.assertRaises(CandidateError):
                verify_session(session, image)

    def test_recalibration_clears_old_pixel_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"image.bin"
            image.write_bytes(b"test")
            session = new_session(image, [600, 700], self.board, "layout")
            add_component(session, "7400", "U1")
            add_wire(session, "W1")
            add_port(session, "A", "input")
            set_calibration(session, self.anchors, self.checks)
            annotate(session, "W1.a", project(self.mapping, self.xy["A10"]))
            with self.assertRaises(CandidateError):
                annotate(session, "U1.1", project(self.mapping, self.xy["A10"]))
            annotate(session, "A", project(self.mapping, self.xy["A10"]))
            set_calibration(session, self.anchors, self.checks)
            self.assertIsNone(session["candidate"]["wires"][0]["a"]["hole"])

    def test_complete_annotation_to_reviewed_not_netlist(self):
        root = Path(__file__).resolve().parents[1]
        original = json.loads((root/"examples/7400-not.candidate.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"image.bin"
            image.write_bytes(b"synthetic-headless-integration-fixture")
            session = new_session(image, [600, 700], self.board, "integration-only", original)
            self.assertIsNone(session["candidate"]["components"][0]["pins"]["1"]["hole"])
            set_calibration(session, self.anchors, self.checks)
            for target, p, _ in endpoints(original):
                annotate(session, target, project(self.mapping, self.xy[p["hole"]]))
            candidate = candidate_from_session(session)
            self.assertIsNone(candidate["reviewed_revision"])
            reviewed = confirm(candidate, self.board, candidate["revision"])
            self.assertTrue(check_not(compile_netlist(reviewed, self.board))["topology_matches"])

    def test_training_labels_do_not_promote_unlabelled_or_model_only_points(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory)/"image.bin"
            image.write_bytes(b"test")
            session = new_session(image, [600, 700], self.board, "layout")
            add_component(session, "7400", "U1")
            add_wire(session, "W1")
            set_calibration(session, self.anchors, self.checks)
            annotate(session, "W1.a", project(self.mapping, self.xy["A10"]))
            annotate(session, "W1.b", visible=False)
            session["candidate"]["components"][0]["pins"]["1"].update(
                source="vision", hole="E10", image_xy=[200, 200])
            with self.assertRaises(CandidateError):
                training_record(session)
            labels = training_record(session, reviewed=True)
            self.assertEqual(labels["wires"][0]["a"]["hole"], "A10")
            self.assertFalse(labels["wires"][0]["b"]["visible"])
            self.assertIsNone(labels["components"][0]["pins"]["1"]["hole"])
            self.assertIsNone(labels["components"][0]["pins"]["2"]["visible"])


if __name__ == "__main__":
    unittest.main()
