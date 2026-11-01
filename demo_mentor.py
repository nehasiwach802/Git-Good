"""Offline ML 3 explanation demonstration; all data is simulated."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from knowledge_lifecycle import KnowledgeStore, Principal
from lab_memory import MemoryServiceError
from mentor import DiagnosticResult, EvidenceItem
from ml3_service import ML3Service


class OfflineMemory:
    def recall(self, student_id, session_id, query):
        raise MemoryServiceError("Simulated memory outage")


def main():
    with TemporaryDirectory() as folder:
        with KnowledgeStore(Path(folder) / "knowledge.sqlite3") as knowledge:
            service = ML3Service(memory=OfflineMemory(), knowledge=knowledge,
                                 outcome_writer=None)
            result = DiagnosticResult(
                session_id="sim-session", suspected_cause="apparatus",
                cause_probabilities={"wiring": 0.1, "concept": 0.2, "apparatus": 0.7},
                evidence=(EvidenceItem("sim-evidence-1", "Confirmed connections match the reference",
                                       "ml2_netlist_diff", "ml2_computed"),),
                limitations=("The instrument has not been verified by an instructor",),
                permitted_next_action="Ask the instructor to compare a known-good probe at node X.")
            reply = service.explain_result(
                Principal("sim-student", "sim-lab", "student"), result,
                query="Earlier RC filter checks", equipment_id="sim-scope", channel="CH2",
                simulated=True, now=datetime.now(timezone.utc))
            print("SIMULATED DEMO - no Qwen or Meko calls")
            print("Explanation:", reply["explanation"])
            print("ML 2 probabilities:", reply["cause_probabilities"])
            print("Evidence IDs:", [item["evidence_id"] for item in reply["evidence"]])
            print("Personal memory status:", reply["context"]["memory_status"])


if __name__ == "__main__":
    main()
