"""Offline demonstration. This fake transport never connects to Meko."""

import json
from uuid import uuid4
from lab_memory import MekoMemory, SessionOutcome


class FakeMeko:
    """Illustrates routing only; not Meko semantic extraction or durable storage."""

    def __init__(self):
        self.memories = {}

    def __call__(self, name, arguments):
        scope = arguments["datapack_id"]
        if name == "conversation_create":
            return {"id": "demo-" + arguments["session_id"]}
        if name == "memory_add":
            row = {"id": str(uuid4()), **json.loads(arguments["text"])}
            self.memories.setdefault(scope, []).append(row)
            return {"results": [{"id": row["id"], "event": "ADD"}]}
        if name == "memory_get_all":
            rows = self.memories.get(scope, [])
            size, page = arguments["page_size"], arguments["page"]
            return {"memories": rows[(page - 1) * size:page * size],
                    "page": page, "page_size": size, "total": len(rows),
                    "total_pages": max(1, (len(rows) + size - 1) // size)}
        if name in ("memory_update", "memory_delete_by_id"):
            rows = self.memories.get(scope, [])
            for index, row in enumerate(rows):
                if row["id"] == arguments["memory_id"]:
                    if name == "memory_update":
                        rows[index] = {"id": row["id"], "memory": arguments["text"]}
                    else:
                        rows.pop(index)
                    return {"message": "success"}
            return {"error": "not_found"}
        if name == "context_search":
            return {"results": {"memory": self.memories.get(scope, []),
                                "knowledge_base": [], "conversation": {"hits": []}}}
        raise ValueError("Unsupported fake tool")


def main():
    memory = MekoMemory(FakeMeko(), {"demo-student-a": "fake-private-a",
                                   "demo-student-b": "fake-private-b"}, "fake-build")
    print("OFFLINE DEMO - all sessions and readings are simulated")
    print("Before:", memory.recall("demo-student-a", "attempt-1", "RC filter"))
    memory.store_outcome("demo-student-a", SessionOutcome(
        session_id="attempt-1", experiment_id="rc-filter", equipment_id="scope-3",
        equipment_channel="CH2", connections_confirmed=True,
        measurements=({"node": "output", "value": 0.2, "unit": "V"},),
        diagnostic_evidence={"source": "mock-ml2", "suspected_cause": "apparatus",
                             "evidence_ids": ["mock-reading-1"]},
        checks_performed=("Confirmed circuit connections",), resolved=False, simulated=True))
    print("Returning student:", memory.recall("demo-student-a", "attempt-2", "RC filter"))
    print("Different student:", memory.recall("demo-student-b", "attempt-3", "RC filter"))
    listing = memory.view_context("demo-student-a", "attempt-2")
    memory_id = listing["memories"][0]["id"]
    print("View context:", listing)
    memory.correct_context("demo-student-a", "attempt-2", memory_id,
                           "Simulated correction: the earlier measurement used the wrong scale.")
    print("After correction:", memory.recall("demo-student-a", "attempt-2", "RC filter"))
    memory.forget_context("demo-student-a", "attempt-2", memory_id)
    print("After forgetting:", memory.recall("demo-student-a", "attempt-2", "RC filter"))


if __name__ == "__main__":
    main()
