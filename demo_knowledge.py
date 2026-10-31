"""Simulated approval/expiry/repair lifecycle in a temporary SQLite database."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from demo_equipment import simulated_evidence
from equipment_flags import flag_equipment
from knowledge_lifecycle import KnowledgeStore, Principal


def main():
    now = datetime.now(timezone.utc)
    instructor = Principal("sim-instructor", "demo-lab", "instructor")
    technician = Principal("sim-technician", "demo-lab", "technician")
    flag = flag_equipment(simulated_evidence(now), as_of=now)[0]
    with TemporaryDirectory() as folder:
        path = Path(folder) / "knowledge.sqlite3"
        with KnowledgeStore(path) as knowledge:
            knowledge.enqueue(flag, now=now)
            knowledge.enqueue(flag, now=now)
            print("SIMULATED DEMO - temporary database, no Meko calls")
            print("Review queue (replay does not duplicate):", len(knowledge.review_queue(instructor)))
            print("Warnings before approval:", knowledge.active_notes(
                "demo-lab", "scope-3", channel="CH2", simulated=True, now=now))
            knowledge.decide(instructor, flag["flag_id"], approve=True,
                             note="Simulated approved warning: CH2 shows a repeated amplitude discrepancy. Ask the instructor to inspect it.",
                             now=now, expires_at=now + timedelta(days=1))
        with KnowledgeStore(path) as knowledge:
            notes = knowledge.active_notes("demo-lab", "scope-3", channel="CH2", simulated=True, now=now)
            print("Warnings after approval and database restart:", len(notes))
            print("Approval provenance:", notes[0])
            print("Warnings at expiry:", len(knowledge.active_notes(
                "demo-lab", "scope-3", channel="CH2", simulated=True, now=now + timedelta(days=1))))
            knowledge.mark_repaired(technician, "scope-3", channel="CH2", simulated=True,
                                    note="Simulated CH2 repair completed", now=now + timedelta(hours=1))
            print("Warnings after repair:", len(knowledge.active_notes(
                "demo-lab", "scope-3", channel="CH2", simulated=True, now=now + timedelta(hours=2))))
            print("Audit actions:", [event["action"] for event in knowledge.history(
                instructor, flag["flag_id"], now=now + timedelta(hours=2))["events"]])


if __name__ == "__main__":
    main()
