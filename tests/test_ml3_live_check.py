import unittest

from demo_memory import FakeMeko
from lab_memory import MekoMemory, MemoryServiceError
from live_memory_check import acceptance_check


class SemanticFake(FakeMeko):
    def __call__(self, name, arguments):
        result = super().__call__(name, arguments)
        if name == "memory_add":
            row = self.memories[arguments["datapack_id"]][-1]
            row["memory"] = "The simulated RC output measured 0.2 V after checking wiring."
        return result


class AcceptanceTests(unittest.TestCase):
    def test_live_listing_data_field_supports_complete_acceptance(self):
        class DataListing(SemanticFake):
            def __call__(self, name, args):
                result = super().__call__(name, args)
                if name == "memory_get_all":
                    result["memories"] = [
                        {"id": row["id"], "data": row["memory"]}
                        for row in result["memories"]]
                return result
        fake = DataListing()
        memory = MekoMemory(fake, {"a": "synthetic-a", "b": "synthetic-b"}, "build")
        reports = []
        acceptance_check(memory, timeout=0.01, interval=0.001, report=reports.append)
        self.assertTrue(any("correction appears" in line for line in reports))
        self.assertEqual(fake.memories["synthetic-a"], [])

    def test_stale_correction_fails_with_structure_only_diagnostics(self):
        class StaleUpdate(SemanticFake):
            def __call__(self, name, args):
                if name == "memory_update":
                    return {"message": "acknowledged"}
                return super().__call__(name, args)
        fake = StaleUpdate()
        memory = MekoMemory(fake, {"a": "synthetic-a", "b": "synthetic-b"}, "build")
        reports = []
        with self.assertRaisesRegex(MemoryServiceError, "corrected memory listing"):
            acceptance_check(memory, timeout=0.002, interval=0.001, report=reports.append)
        diagnostic = " ".join(line for line in reports if line.startswith("DIAGNOSTIC"))
        self.assertIn("target_present=True", diagnostic)
        self.assertIn("memory_exact_match=False", diagnostic)
        self.assertNotIn("0.2 V", diagnostic)
        self.assertEqual(fake.memories["synthetic-a"], [])

    def test_complete_flow_and_cleanup_offline(self):
        fake = SemanticFake()
        reports = []
        memory = MekoMemory(fake, {"a": "synthetic-a", "b": "synthetic-b"}, "build")
        acceptance_check(memory, timeout=0.01, interval=0.001, report=reports.append)
        self.assertEqual(fake.memories["synthetic-a"], [])
        self.assertEqual(len(reports), 6)

    def test_existing_data_blocks_writes_and_cleanup(self):
        fake = SemanticFake()
        fake.memories["synthetic-a"] = [{"id": "existing", "memory": "Leave alone"}]
        memory = MekoMemory(fake, {"a": "synthetic-a", "b": "synthetic-b"}, "build")
        with self.assertRaises(ValueError):
            acceptance_check(memory, report=lambda *_: None)
        self.assertEqual(fake.memories["synthetic-a"][0]["memory"], "Leave alone")

    def test_empty_extraction_does_not_report_success(self):
        class NoExtraction(SemanticFake):
            def __call__(self, name, args):
                if name == "memory_add":
                    return {"results": []}
                return super().__call__(name, args)
        memory = MekoMemory(NoExtraction(), {"a": "synthetic-a", "b": "synthetic-b"}, "build")
        with self.assertRaises(MemoryServiceError):
            acceptance_check(memory, timeout=0.002, interval=0.001, report=lambda *_: None)
