import copy
from pathlib import Path
import tempfile
import unittest

from labvision.annotation import (new_session, add_component, add_wire, annotate,
                                 set_calibration, training_record)
from labvision.assistance import prepare_draft, accept_object_draft
from labvision.core import CandidateError, make_board
from labvision.geometry import board_fingerprint


class AssistanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        image = Path(self.temp.name)/"photo.bin"
        image.write_bytes(b"image identity")
        self.session = new_session(image, [400, 400], make_board(10), "test")
        add_component(self.session, "7400", "U1")
        set_calibration(self.session,
            [{"hole": h, "xy": xy} for h, xy in
             [("A1", [100, 100]), ("J1", [320, 100]),
              ("J10", [320, 280]), ("A10", [100, 280])]],
            [{"hole": "A5", "xy": [100, 180]}, {"hole": "J5", "xy": [320, 180]}])
        self.observations = {
            "image_sha256": self.session["image_sha256"],
            "calibration_fingerprint": board_fingerprint(self.session["board"]),
            "objects": [{"kind": "wire", "id": "W1"}],
            "outer_holes": [{"id": "R1", "xy": [60, 140]}],
            "endpoints": [
                {"target": "W1.a", "xy": [60, 140], "visible": True, "reason": "visible rail end"},
                {"target": "W1.b", "xy": [100, 140], "visible": True, "reason": "visible end"},
                {"target": "U1.1", "projected_hole": "E5", "visible": None, "reason": "pose projection"}]}

    def test_draft_is_separate_and_does_not_export_guesses_as_training_truth(self):
        before = copy.deepcopy(self.session)
        draft = prepare_draft(self.session, self.observations)
        self.assertEqual(self.session, before)
        labels = training_record(draft, reviewed=True)
        self.assertIsNone(labels["wires"][0]["a"]["hole"])
        self.assertFalse(labels["wires"][0]["pairing_reviewed"])
        self.assertEqual(accept_object_draft(draft, "W1"), 2)
        self.assertEqual(accept_object_draft(draft, "U1"), 1)
        labels = training_record(draft, reviewed=True)
        self.assertEqual(labels["wires"][0]["a"]["hole"], "R1")
        self.assertTrue(labels["wires"][0]["pairing_reviewed"])
        self.assertIsNone(labels["components"][0]["pins"]["1"]["visible"])
        self.assertIsNone(labels["components"][0]["pins"]["1"]["hole"])

    def test_existing_manual_labels_are_preserved_and_wrong_image_rejected(self):
        add_wire(self.session, "W1")
        annotate(self.session, "W1.a", [120, 140])
        draft = prepare_draft(self.session, self.observations)
        self.assertEqual(draft["candidate"]["wires"][0]["a"]["hole"], "B3")
        self.observations["image_sha256"] = "another-image"
        with self.assertRaises(CandidateError):
            prepare_draft(self.session, self.observations)

    def test_unknown_end_stays_unknown_and_pairing_unreviewed(self):
        self.observations["endpoints"][1].update(unresolved=True)
        draft = prepare_draft(self.session, self.observations)
        self.assertEqual(accept_object_draft(draft, "W1"), 1)
        self.assertIsNone(draft["candidate"]["wires"][0]["b"]["hole"])
        self.assertFalse(draft["candidate"]["wires"][0]["pairing_reviewed"])


if __name__ == "__main__":
    unittest.main()
