from dataclasses import replace
import json
import unittest

from demo_memory import FakeMeko
from lab_memory import MemoryServiceError, MekoMemory, SessionOutcome


def outcome():
    return SessionOutcome("s1", "rc", "scope-3", "CH2", True,
                          ({"node": "out", "value": 0.2, "unit": "V"},),
                          {"source": "mock-ml2", "evidence_ids": ["e1"]},
                          ("Confirmed wiring",), False, True)


class MemoryTests(unittest.TestCase):
    def test_listing_normalizes_data_without_overwriting_existing_memory(self):
        rows = [{"id": "first", "data": "Stored fact"},
                {"id": "second", "memory": "Canonical", "data": "Other"}]
        def transport(name, args):
            if name == "conversation_create":
                return {"id": "server-id"}
            return {"memories": rows, "total_pages": 1}
        memory = MekoMemory(transport, {"a": "private-a"}, "build")
        listing = memory.view_context("a", "s1")
        self.assertEqual(listing["memories"][0]["memory"], "Stored fact")
        self.assertEqual(listing["memories"][0]["data"], "Stored fact")
        self.assertEqual(listing["memories"][1]["memory"], "Canonical")
        self.assertNotIn("memory", rows[0])

    def setUp(self):
        self.fake = FakeMeko()
        self.memory = MekoMemory(self.fake, {"a": "private-a", "b": "private-b"}, "build")

    def test_outcome_round_trip_and_student_isolation(self):
        self.memory.store_outcome("a", outcome())
        recalled = self.memory.recall("a", "s2", "rc")
        self.assertEqual(recalled["memory"][0]["diagnostic_evidence"]["evidence_ids"], ["e1"])
        self.assertTrue(recalled["memory"][0]["simulated"])
        self.assertEqual(self.memory.recall("b", "s3", "rc")["memory"], [])

    def test_forbidden_or_ambiguous_scopes(self):
        for scopes in ({"a": "build"}, {"a": "same", "b": "same"}, {"a": ""}):
            with self.assertRaises(ValueError):
                MekoMemory(self.fake, scopes, "build")
        with self.assertRaises(ValueError):
            self.memory.recall("unknown", "s1", "rc")
        self.assertEqual(self.fake.memories, {})

    def test_reject_invalid_measurements_and_flags(self):
        for changes in ({"measurements": ({"node": "out", "value": float("nan"), "unit": "V"},)},
                        {"measurements": ({"node": "out", "value": 1},)},
                        {"simulated": "false"}, {"session_id": " "}):
            with self.assertRaises(ValueError):
                replace(outcome(), **changes)

    def test_uses_server_conversation_id_and_explicit_datapack(self):
        calls = []

        def transport(name, args):
            calls.append((name, args))
            if name == "conversation_create":
                return {"structuredContent": {"result": json.dumps({"id": "server-id"})}}
            return {"content": [{"type": "text", "text": '{"results": {"memory": []}}'}]}

        memory = MekoMemory(transport, {"a": "private-a"}, "build")
        memory.recall("a", "local-session", "rc")
        self.assertEqual(calls[1][1]["conversation_id"], "server-id")
        self.assertTrue(all(args["datapack_id"] == "private-a" for _, args in calls))

    def test_service_errors_are_not_empty_successes(self):
        for response in ({"error": "unavailable"}, {"isError": True},
                         {"structuredContent": {"result": '{"error": "denied"}'}}, {}):
            memory = MekoMemory(lambda *_: response, {"a": "private-a"}, "build")
            with self.assertRaises(MemoryServiceError):
                memory.recall("a", "s1", "rc")

    def test_transport_failure(self):
        def unavailable(*_):
            raise TimeoutError("unavailable")
        memory = MekoMemory(unavailable, {"a": "private-a"}, "build")
        with self.assertRaises(MemoryServiceError):
            memory.store_outcome("a", outcome())

    def test_view_correct_forget_change_subsequent_recall(self):
        self.memory.store_outcome("a", outcome())
        row = self.memory.view_context("a", "s1")["memories"][0]
        self.memory.correct_context("a", "s1", row["id"], "Earlier scale reading was wrong")
        recalled = self.memory.recall("a", "s2", "scale")["memory"]
        self.assertEqual(recalled[0]["memory"], "Earlier scale reading was wrong")
        self.memory.forget_context("a", "s1", row["id"])
        self.assertEqual(self.memory.recall("a", "s2", "scale")["memory"], [])

    def test_cannot_correct_or_forget_another_students_memory(self):
        self.memory.store_outcome("a", outcome())
        memory_id = self.memory.view_context("a", "s1")["memories"][0]["id"]
        for action in (lambda: self.memory.correct_context("b", "s1", memory_id, "wrong"),
                       lambda: self.memory.forget_context("b", "s1", memory_id)):
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(len(self.memory.recall("a", "s2", "rc")["memory"]), 1)

    def test_controls_follow_listing_pagination(self):
        for _ in range(101):
            self.memory.store_outcome("a", outcome())
        listing = self.memory.view_context("a", "s1", page=2, page_size=100)
        self.assertEqual(len(listing["memories"]), 1)
        memory_id = listing["memories"][0]["id"]
        self.memory.forget_context("a", "s1", memory_id)
        self.assertEqual(self.memory.view_context("a", "s1")["total"], 100)

    def test_session_scope_and_memory_only_recall(self):
        calls = []
        def transport(name, args):
            calls.append((name, args))
            return self.fake(name, args)
        memory = MekoMemory(transport, {"a": "private-a", "b": "private-b"}, "build")
        a = memory.start_session("a", "same-label")
        b = memory.start_session("b", "same-label")
        self.assertNotEqual(a, b)
        self.assertEqual(a, memory.start_session("a", "same-label"))
        memory.recall("a", "same-label", "rc")
        self.assertEqual(calls[-1][1]["force_source"], "memory")

    def test_bad_control_inputs_fail(self):
        with self.assertRaises(ValueError):
            self.memory.forget_context("a", "s1", "not-a-uuid")
        with self.assertRaises(ValueError):
            self.memory.correct_context("a", "s1", "unused", " ")
        with self.assertRaises(ValueError):
            self.memory.view_context("a", "s1", page=0)
        with self.assertRaises(ValueError):
            self.memory.view_context("a", "s1", page_size=101)

    def test_revalidate_mutated_outcome_before_remote_call(self):
        changed = outcome()
        changed.measurements[0]["value"] = float("inf")
        with self.assertRaises(ValueError):
            self.memory.store_outcome("a", changed)
        self.assertEqual(self.fake.memories, {})

    def test_null_structured_content_uses_text(self):
        def transport(name, args):
            result = {"id": "server-id"} if name == "conversation_create" else {"results": {"memory": []}}
            return {"structuredContent": None,
                    "content": [{"type": "text", "text": json.dumps(result)}]}
        memory = MekoMemory(transport, {"a": "private-a"}, "build")
        self.assertEqual(memory.recall("a", "s1", "rc"), {"memory": []})


if __name__ == "__main__":
    unittest.main()
