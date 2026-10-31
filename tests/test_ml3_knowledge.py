from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from demo_equipment import simulated_evidence
from equipment_flags import flag_equipment
from knowledge_lifecycle import KnowledgeStore, Principal


NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "knowledge.sqlite3"
        self.store = KnowledgeStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.instructor = Principal("teacher", "demo-lab", "instructor")
        self.technician = Principal("tech", "demo-lab", "technician")
        self.student = Principal("student", "demo-lab", "student")
        self.flag = flag_equipment(simulated_evidence(NOW), as_of=NOW)[0]

    def enqueue(self, flag=None, now=NOW):
        return self.store.enqueue(flag or self.flag, now=now)

    def approve(self, actor=None, now=NOW, **changes):
        args = dict(approve=True, note="Instructor verified equipment warning", now=now,
                    expires_at=NOW + timedelta(days=1))
        args.update(changes)
        return self.store.decide(actor or self.instructor, self.flag["flag_id"], **args)

    def notes(self, **changes):
        args = dict(channel="CH2", simulated=True, now=NOW)
        args.update(changes)
        return self.store.active_notes("demo-lab", "scope-3", **args)

    def repair(self, **changes):
        args = dict(channel="CH2", simulated=True, note="Repair completed", now=NOW + timedelta(hours=1))
        args.update(changes)
        return self.store.mark_repaired(self.technician, "scope-3", **args)

    def test_pending_is_private_and_replay_deduplicates(self):
        self.enqueue()
        self.enqueue()
        self.assertEqual(len(self.store.review_queue(self.instructor)), 1)
        self.assertEqual(self.notes(), [])
        self.assertEqual(len(self.store.history(self.instructor, self.flag["flag_id"], now=NOW)["events"]), 1)

    def test_approval_provenance_and_exact_expiry(self):
        self.enqueue()
        self.approve()
        note = self.notes()[0]
        self.assertEqual(note["approved_by"], "teacher")
        self.assertEqual(len(note["supporting_evidence_ids"]), 3)
        self.assertEqual(note["layer"], "instructor_verified")
        self.assertEqual(self.notes(now=NOW + timedelta(days=1)), [])
        self.assertEqual(self.store.history(self.instructor, self.flag["flag_id"], now=NOW + timedelta(days=1))["status"], "expired")

    def test_database_restart_preserves_approval(self):
        self.enqueue()
        self.approve()
        with KnowledgeStore(self.path) as reopened:
            self.assertEqual(len(reopened.active_notes("demo-lab", "scope-3", channel="CH2", simulated=True, now=NOW)), 1)

    def test_roles_and_lab_isolation(self):
        self.enqueue()
        for actor in (self.student, self.technician, Principal("outsider", "other-lab", "instructor")):
            with self.assertRaises(PermissionError):
                self.approve(actor)
        with self.assertRaises(PermissionError):
            self.store.review_queue(self.student)
        with self.assertRaises(PermissionError):
            self.store.mark_repaired(self.instructor, "scope-3", simulated=True, note="repair", now=NOW)
        self.assertEqual(self.store.review_queue(Principal("other", "other-lab", "instructor")), [])

    def test_rejection_stays_hidden_and_cannot_be_approved(self):
        self.enqueue()
        self.store.decide(self.instructor, self.flag["flag_id"], approve=False, note="Insufficient evidence", now=NOW)
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.store.review_queue(self.instructor), [])
        with self.assertRaises(ValueError):
            self.approve()

    def test_approval_requires_note_and_future_expiry(self):
        self.enqueue()
        for changes in ({"expires_at": None}, {"expires_at": NOW}, {"note": " "}):
            with self.assertRaises(ValueError):
                self.approve(**changes)
        self.assertEqual(len(self.store.review_queue(self.instructor)), 1)

    def test_repair_retires_and_replay_cannot_reactivate(self):
        self.enqueue()
        self.approve()
        self.assertEqual(self.repair(), 1)
        self.assertEqual(self.notes(now=NOW + timedelta(hours=2)), [])
        self.assertEqual(self.enqueue(now=NOW + timedelta(hours=2))["status"], "retired")
        record = self.store.history(self.instructor, self.flag["flag_id"], now=NOW + timedelta(hours=2))
        self.assertEqual(record["retirement"]["actor_id"], "tech")
        self.assertEqual([event["action"] for event in record["events"]], ["submitted", "approved", "retired"])

    def test_repair_retires_pending_queue_entries(self):
        self.enqueue()
        self.repair()
        self.assertEqual(self.store.review_queue(self.instructor), [])
        with self.assertRaises(ValueError):
            self.approve(now=NOW + timedelta(hours=2))

    def test_instructor_can_withdraw_incorrect_warning_without_claiming_repair(self):
        self.enqueue()
        self.approve()
        with self.assertRaises(PermissionError):
            self.store.withdraw(self.student, self.flag["flag_id"], note="incorrect", now=NOW)
        self.store.withdraw(self.instructor, self.flag["flag_id"],
                            note="Supporting measurement was corrected", now=NOW)
        self.assertEqual(self.notes(), [])
        record = self.store.history(self.instructor, self.flag["flag_id"], now=NOW)
        self.assertEqual(record["retirement"]["reason"], "instructor_withdrawn")
        self.assertEqual(record["events"][-1]["action"], "withdrawn")

    def test_repaired_old_evidence_cannot_create_new_flag_but_fresh_can(self):
        self.repair()
        old = simulated_evidence(NOW)
        old[0] = replace(old[0], evidence_id="new-id-same-old-reading")
        old_flag = flag_equipment(old, as_of=NOW + timedelta(hours=2))[0]
        with self.assertRaises(ValueError):
            self.enqueue(old_flag, now=NOW + timedelta(hours=2))
        fresh = flag_equipment(simulated_evidence(NOW + timedelta(hours=2)), as_of=NOW + timedelta(hours=2))[0]
        self.enqueue(fresh, now=NOW + timedelta(hours=2))
        self.assertEqual(len(self.store.review_queue(self.instructor)), 1)

    def test_channel_and_simulation_isolation(self):
        self.enqueue()
        self.approve()
        self.assertEqual(self.notes(channel="CH1"), [])
        self.assertEqual(self.notes(simulated=False), [])
        self.repair(channel="CH1")
        self.repair(simulated=False)
        self.assertEqual(len(self.notes()), 1)
        self.repair(channel=None)
        self.assertEqual(self.notes(now=NOW + timedelta(hours=2)), [])

    def test_conflicting_payload_and_future_evidence_are_rejected(self):
        self.enqueue()
        bad = deepcopy(self.flag)
        bad["reason"] = "Different payload"
        with self.assertRaises(ValueError):
            self.enqueue(bad)
        future = flag_equipment(simulated_evidence(NOW + timedelta(hours=1)), as_of=NOW + timedelta(hours=1))[0]
        with self.assertRaises(ValueError):
            self.enqueue(future)

    def test_returned_payload_is_detached_and_audit_is_preserved(self):
        record = self.enqueue()
        record["candidate"]["supporting_sessions"].clear()
        self.approve()
        saved = self.store.history(self.instructor, self.flag["flag_id"], now=NOW)
        self.assertEqual(len(saved["candidate"]["supporting_sessions"]), 3)
        self.assertEqual(saved["events"][1]["actor_id"], "teacher")

    def test_review_and_repair_cannot_be_backdated(self):
        self.enqueue()
        with self.assertRaises(ValueError):
            self.approve(now=NOW - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            self.repair(now=NOW - timedelta(seconds=1))
        self.assertEqual(len(self.store.review_queue(self.instructor)), 1)
