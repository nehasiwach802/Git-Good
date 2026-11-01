from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from equipment_flags import EquipmentEvidence, FlagPolicy, flag_equipment
from lab_memory import SessionOutcome


NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def observation(index, **changes):
    row = EquipmentEvidence(
        f"reading-{index}", "lab", f"student-{index}", f"session-{index}",
        "rc" if index % 2 else "opamp", "scope-3", "CH2", "voltage_amplitude_peak",
        1.0, 0.5, 0.05, "V", NOW, True, True, True)
    return replace(row, **changes)


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.rows = [observation(i) for i in (1, 2, 3)]

    def flags(self, rows, **kwargs):
        return flag_equipment(rows, as_of=NOW, **kwargs)

    def test_threshold_and_evidence_provenance(self):
        self.assertEqual(self.flags(self.rows[:2]), [])
        flag = self.flags(self.rows)[0]
        self.assertEqual(flag["status"], "pending_review")
        self.assertEqual(flag["session_count"], 3)
        self.assertEqual(flag["student_count"], 3)
        self.assertEqual(flag["experiment_ids"], ["opamp", "rc"])
        self.assertEqual({r["evidence_id"] for r in flag["supporting_sessions"]},
                         {r.evidence_id for r in self.rows})
        self.assertNotIn("probability", flag)
        self.assertTrue(flag["simulated"])
        self.assertNotIn("student_id", flag["supporting_sessions"][0])

    def test_replays_and_multiple_readings_in_session_do_not_inflate_count(self):
        duplicate = replace(self.rows[0], evidence_id="extra-reading")
        flags = self.flags([*self.rows, self.rows[0], duplicate])
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["session_count"], 3)
        self.assertEqual(self.flags([self.rows[0]] * 20), [])

    def test_one_student_or_one_experiment_is_insufficient(self):
        self.assertEqual(self.flags([replace(r, student_id="one") for r in self.rows]), [])
        self.assertEqual(self.flags([replace(r, experiment_id="rc") for r in self.rows]), [])

    def test_equipment_channel_lab_metric_and_mode_boundaries(self):
        for changes in ({"equipment_id": "scope-4"}, {"channel": "CH1"},
                        {"lab_id": "other-lab"}, {"metric": "voltage_rms"},
                        {"simulated": False}, {"unit": "A"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.flags([*self.rows[:2], replace(self.rows[2], **changes)]), [])

    def test_wrong_or_unconfirmed_circuits_are_excluded(self):
        for changes in ({"connections_confirmed": False}, {"netlist_matches_reference": False}):
            self.assertEqual(self.flags([*self.rows[:2], replace(self.rows[2], **changes)]), [])

    def test_normal_readings_and_tolerance_boundary_are_excluded(self):
        self.assertEqual(self.flags([replace(r, observed=1.0) for r in self.rows]), [])
        # Exactly at the tolerance is not an anomaly.
        self.assertEqual(self.flags([replace(r, expected=1.0, observed=0.5, tolerance=0.5)
                                     for r in self.rows]), [])

    def test_relative_error_compares_different_experiments_and_units(self):
        rows = [self.rows[0], replace(self.rows[1], expected=2.0, observed=1.0, tolerance=0.1),
                replace(self.rows[2], expected=1000, observed=500, tolerance=50, unit="mV")]
        flag = self.flags(rows)[0]
        self.assertEqual(flag["relative_error_range"], [-0.5, -0.5])
        self.assertEqual(flag["unit"], "V")
        self.assertEqual(flag["supporting_sessions"][2]["unit"], "mV")

    def test_different_direction_and_dissimilar_magnitudes_do_not_merge(self):
        for observed in (1.5, 0.1):
            self.assertEqual(self.flags([*self.rows[:2], replace(self.rows[2], observed=observed)]), [])

    def test_similarity_does_not_chain_across_large_spread(self):
        rows = [replace(r, observed=value) for r, value in zip(self.rows, (0.3, 0.44, 0.58))]
        self.assertEqual(self.flags(rows), [])

    def test_outlier_does_not_hide_later_valid_cluster(self):
        rows = [observation(4, observed=0.1), *self.rows]
        flags = self.flags(rows)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["session_count"], 3)

    def test_time_window_future_and_timezone_validation(self):
        for timestamp in (NOW - timedelta(days=8), NOW + timedelta(seconds=1)):
            self.assertEqual(self.flags([*self.rows[:2], replace(self.rows[2], observed_at=timestamp)]), [])
        rows = [replace(r, observed_at=NOW - timedelta(days=7)) for r in self.rows]
        self.assertEqual(len(self.flags(rows)), 1)
        with self.assertRaises(ValueError):
            flag_equipment(self.rows, as_of=NOW.replace(tzinfo=None))

    def test_conflicting_ids_and_session_experiments_are_rejected(self):
        with self.assertRaises(ValueError):
            self.flags([*self.rows, replace(self.rows[0], observed=0.3)])
        with self.assertRaises(ValueError):
            self.flags([*self.rows, replace(self.rows[0], evidence_id="new", experiment_id="other")])

    def test_deterministic_output_and_configurable_policy(self):
        self.assertEqual(self.flags(self.rows), self.flags(reversed(self.rows)))
        self.assertEqual(self.flags(self.rows, policy=FlagPolicy(min_students=4)), [])
        for changes in ({"min_students": 1}, {"max_error_spread": float("nan")}, {"lookback_days": 0}):
            with self.assertRaises(ValueError):
                FlagPolicy(**changes)

    def test_bad_evidence_is_rejected_and_zero_reference_is_finite(self):
        for changes in ({"observed": float("nan")}, {"expected": float("inf")},
                        {"tolerance": 0}, {"unit": "unknown"}, {"simulated": "yes"},
                        {"observed_at": NOW.replace(tzinfo=None)}, {"channel": " CH2"}):
            with self.assertRaises(ValueError):
                replace(self.rows[0], **changes)
        self.assertEqual(observation(1, expected=0, observed=0.1, tolerance=0.05).relative_error, 2.0)

    def test_session_outcome_bridge_preserves_measured_evidence(self):
        outcome = SessionOutcome("s", "rc", "scope-3", "CH2", True,
                                 ({"node": "out", "value": 0.5, "unit": "V"},),
                                 {"source": "mock-ml2"}, (), False, True)
        row = EquipmentEvidence.from_outcome(
            outcome, evidence_id="e", lab_id="lab", student_id="pseudonymous-student",
            measurement_index=0, expected=1, tolerance=0.05, metric="voltage_amplitude_peak",
            observed_at=NOW, netlist_matches_reference=True)
        self.assertEqual(row.observed, 0.5)
        self.assertTrue(row.connections_confirmed)
        self.assertEqual(row.session_id, outcome.session_id)
