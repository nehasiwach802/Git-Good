from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from demo_memory import FakeMeko
from knowledge_lifecycle import KnowledgeStore, Principal
from lab_memory import MekoMemory, MemoryServiceError, SessionOutcome
from mentor import DiagnosticResult, EvidenceItem, explain_diagnostic
from ml3_service import ML3Service
from outcome_writer import OutcomeWriter
from qwen_transport import QwenTransport


NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def diagnostic(action="Measure the output at node X with the instructor present"):
    return DiagnosticResult("s1", "apparatus", {"wiring": 0.1, "concept": 0.2, "apparatus": 0.7},
                            (EvidenceItem("e1", "Confirmed wiring matches the reference", "ml2", "ml2_computed"),),
                            ("Instrument fault is suspected, not verified",), action)


def outcome():
    return SessionOutcome("s1", "rc", "scope-3", "CH2", True,
                          ({"node": "X", "value": 0.2, "unit": "V"},),
                          {"source": "ml2", "evidence_ids": ["e1"]}, (), False, True)


class MentorTests(unittest.TestCase):
    def test_explanation_preserves_ml2_fields_and_uncertainty(self):
        result = explain_diagnostic(diagnostic(), context={"personal": [], "approved_equipment": [],
                                                   "memory_status": "unavailable"})
        self.assertEqual(result["suspected_cause"], "apparatus")
        self.assertEqual(result["cause_probabilities"]["apparatus"], 0.7)
        self.assertEqual(result["next_action"], diagnostic().permitted_next_action)
        self.assertIn("not verified", result["explanation"])
        self.assertEqual(result["evidence"][0]["evidence_id"], "e1")
        self.assertEqual(result["context"]["memory_status"], "unavailable")

    def test_hard_safety_gate_prevents_model_call(self):
        called = []
        for action in ("Probe mains voltage", "Touch a large capacitor", "Touch large capacitors",
                       "Try live probing", "Probe a live wire"):
            response = explain_diagnostic(diagnostic(action), generate=lambda _: called.append(True))
            self.assertEqual(response["status"], "refused")
            self.assertEqual(response["next_action"], "Ask your instructor for help.")
        self.assertEqual(called, [])

    def test_model_receives_structure_and_cannot_replace_diagnosis(self):
        messages = []
        response = explain_diagnostic(diagnostic(), generate=lambda value: messages.extend(value) or "Please ask the instructor to check the instrument.")
        self.assertIn("permitted_next_action", messages[1]["content"])
        self.assertIn("probabilities", messages[1]["content"])
        self.assertEqual(response["cause_probabilities"]["apparatus"], 0.7)
        self.assertEqual(response["next_action"], diagnostic().permitted_next_action)
        self.assertEqual(response["wording_source"], "model_supplement")
        self.assertIn("an apparatus issue", response["explanation"])

    def test_qwen_payload_omits_personal_history(self):
        messages = []
        explain_diagnostic(diagnostic(), context={"personal": [{"text": "Private student memory"}],
                                                  "approved_equipment": [], "memory_status": "available"},
                           generate=lambda supplied: messages.extend(supplied) or "Please ask the instructor.")
        self.assertNotIn("Private student memory", messages[1]["content"])

    def test_model_failure_uses_template(self):
        def broken(_):
            raise RuntimeError("offline")
        response = explain_diagnostic(diagnostic(), generate=broken)
        self.assertEqual(response["wording_source"], "template")
        self.assertEqual(response["model_status"], "unavailable")

    def test_overconfident_model_wording_is_not_exposed(self):
        response = explain_diagnostic(diagnostic(), generate=lambda _: "The instrument is definitely broken.")
        self.assertNotIn("optional_wording", response)
        self.assertEqual(response["wording_source"], "template")

    def test_invalid_ml2_result_rejected(self):
        with self.assertRaises(ValueError):
            DiagnosticResult("s", "apparatus", {"wiring": 1}, (), (), "check")
        with self.assertRaises(ValueError):
            DiagnosticResult("s", "certain_fault", {"wiring": .1, "concept": .2, "apparatus": .7}, (), (), "check")

    def test_authorized_context_and_memory_failure_preserve_session(self):
        with TemporaryDirectory() as folder:
            with KnowledgeStore(Path(folder) / "k.sqlite3") as knowledge:
                class FailedMemory:
                    def recall(self, *_):
                        raise MemoryServiceError("offline")
                class NoWrite:
                    pass
                service = ML3Service(memory=FailedMemory(), knowledge=knowledge, outcome_writer=NoWrite())
                student = Principal("student-a", "lab", "student")
                ctx = service.retrieve_context(student, session_id="s1", query="RC", equipment_id="scope-3",
                                               channel="CH2", simulated=True, now=NOW)
                self.assertEqual(ctx["memory_status"], "unavailable")
                response = service.explain_result(student, diagnostic(), query="RC",
                                                  equipment_id="scope-3", channel="CH2",
                                                  simulated=True, now=NOW)
                self.assertEqual(response["session_id"], "s1")
                self.assertEqual(response["next_action"], diagnostic().permitted_next_action)
                with self.assertRaises(PermissionError):
                    service.retrieve_context(Principal("teacher", "lab", "instructor"), session_id="s1",
                                             query="RC", equipment_id="scope-3", channel="CH2",
                                             simulated=True, now=NOW)

    def test_personal_claims_are_unverified(self):
        with TemporaryDirectory() as folder:
            class SearchShapedFake(FakeMeko):
                def __call__(self, name, arguments):
                    response = super().__call__(name, arguments)
                    if name == "context_search":
                        response["results"]["memory"] = [
                            {**row, "memory": "A student's unverified recollection",
                             "agent_id": "lab_mentor", "created_at": "2026-10-31T00:00:00Z"}
                            for row in response["results"]["memory"]]
                    return response
            fake = SearchShapedFake()
            memory = MekoMemory(fake, {"student-a": "private-a"}, "build")
            memory.store_outcome("student-a", outcome())
            with KnowledgeStore(Path(folder) / "k.sqlite3") as knowledge:
                service = ML3Service(memory=memory, knowledge=knowledge, outcome_writer=None)
                ctx = service.retrieve_context(Principal("student-a", "lab", "student"), session_id="s2",
                                               query="RC", equipment_id="scope-3", channel="CH2",
                                               simulated=True, now=NOW)
                self.assertEqual(ctx["personal"][0]["verification"], "unverified")
                self.assertEqual(ctx["personal"][0]["origin"]["agent_id"], "lab_mentor")

    def test_qwen_http_request_uses_supplied_model_and_messages(self):
        import httpx
        requests = []
        def fake_post(url, **kwargs):
            requests.append((url, kwargs))
            return httpx.Response(200, json={"choices": [{"message": {"content": "A short explanation."}}]},
                                  request=httpx.Request("POST", url))
        with patch("httpx.post", side_effect=fake_post):
            text = QwenTransport("https://qwen.example/compatible-mode/v1", "secret", "qwen-test")(
                [{"role": "user", "content": "test"}])
        self.assertEqual(text, "A short explanation.")
        self.assertEqual(requests[0][1]["json"]["model"], "qwen-test")
        self.assertEqual(requests[0][1]["headers"]["Authorization"], "Bearer secret")


class WriterTests(unittest.TestCase):
    def test_old_ledger_schema_migrates_without_removing_retry_guard(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "old.sqlite3"
            db = sqlite3.connect(path)
            try:
                db.execute("""CREATE TABLE outcome_submissions (
                    student_id TEXT NOT NULL, session_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY(student_id,session_id))""")
                db.commit()
            finally:
                db.close()
            class NoWrite:
                def store_outcome(self, *_):
                    raise AssertionError("Should not write")
            with OutcomeWriter(path, NoWrite()) as writer:
                self.assertIsNone(writer.local_outcome("student", "missing"))

    def test_replay_and_restart_do_not_repeat_write(self):
        with TemporaryDirectory() as folder:
            class Memory:
                calls = 0
                def store_outcome(self, *_):
                    self.calls += 1
            memory = Memory()
            path = Path(folder) / "outcomes.sqlite3"
            with OutcomeWriter(path, memory) as writer:
                self.assertEqual(writer.submit("student", outcome())["status"], "stored")
                self.assertEqual(writer.submit("student", outcome())["status"], "already_stored")
            with OutcomeWriter(path, memory) as writer:
                self.assertEqual(writer.submit("student", outcome())["status"], "already_stored")
            self.assertEqual(memory.calls, 1)

    def test_uncertain_failure_blocks_automatic_retry(self):
        with TemporaryDirectory() as folder:
            class Memory:
                calls = 0
                def store_outcome(self, *_):
                    self.calls += 1
                    raise MemoryServiceError("timeout after possible write")
            memory = Memory()
            with OutcomeWriter(Path(folder) / "outcomes.sqlite3", memory) as writer:
                with self.assertRaises(MemoryServiceError):
                    writer.submit("student", outcome())
                self.assertEqual(writer.submit("student", outcome())["status"], "needs_reconciliation")
                local = writer.local_outcome("student", "s1")
                self.assertEqual(local["status"], "attempted")
                self.assertEqual(local["outcome"]["measurements"][0]["value"], 0.2)
            self.assertEqual(memory.calls, 1)


if __name__ == "__main__":
    unittest.main()
