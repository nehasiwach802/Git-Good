from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from demo_equipment import simulated_evidence
from demo_memory import FakeMeko
from equipment_flags import flag_equipment
from knowledge_lifecycle import KnowledgeStore, Principal
from lab_memory import MekoMemory, SessionOutcome
from mentor import DiagnosticResult, EvidenceItem
from ml3_http import create_ml3_app
from ml3_service import ML3Service
from outcome_writer import OutcomeWriter


class HttpFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.knowledge_path = root / "knowledge.sqlite3"
        self.writer_path = root / "outcomes.sqlite3"
        self.fake = FakeMeko()
        self.calls = {"diagnostic": 0, "outcome": 0}
        now = datetime.now(timezone.utc)
        self.flag = flag_equipment(simulated_evidence(now), as_of=now)[0]
        with KnowledgeStore(self.knowledge_path) as db:
            db.enqueue(self.flag, now=now)

        @contextmanager
        def factory():
            memory = MekoMemory(self.fake, {"student-a": "scope-a"}, "build")
            with KnowledgeStore(self.knowledge_path) as knowledge:
                with OutcomeWriter(self.writer_path, memory) as writer:
                    yield ML3Service(memory=memory, knowledge=knowledge, outcome_writer=writer)

        def resolve(request):
            token = request.headers.get("authorization", "")
            identities = {"Bearer student": Principal("student-a", "demo-lab", "student"),
                          "Bearer teacher": Principal("teacher", "demo-lab", "instructor"),
                          "Bearer tech": Principal("tech", "demo-lab", "technician")}
            if token not in identities:
                raise PermissionError("No matching test identity")
            return identities[token]

        def authorize(principal, session_id, equipment_id, channel, simulated):
            return (principal.actor_id == "student-a" and session_id == "s1" and
                    equipment_id == "scope-3" and channel == "CH2" and simulated is True)

        def diagnostic(principal, session_id):
            self.calls["diagnostic"] += 1
            return DiagnosticResult(session_id, "apparatus",
                {"wiring": .1, "concept": .2, "apparatus": .7},
                (EvidenceItem("e1", "Confirmed reference circuit", "ml2", "ml2_computed"),),
                ("Instrument not verified",), "Ask the instructor to compare the probe.")

        def outcome(principal, session_id):
            self.calls["outcome"] += 1
            return SessionOutcome(session_id, "rc", "scope-3", "CH2", True,
                ({"node": "out", "value": 0.2, "unit": "V"},),
                {"source": "trusted-ml2", "evidence_ids": ["e1"]}, (), False, True)

        self.client = TestClient(create_ml3_app(
            service_factory=factory, resolve_principal=resolve,
            authorize_session=authorize, resolve_diagnostic=diagnostic,
            resolve_outcome=outcome))
        self.addCleanup(self.client.close)
        self.student = {"Authorization": "Bearer student"}
        self.teacher = {"Authorization": "Bearer teacher"}
        self.tech = {"Authorization": "Bearer tech"}
        self.params = {"equipment_id": "scope-3", "channel": "CH2", "simulated": True}

    def test_student_flow_review_and_repair(self):
        base = "/sessions/s1"
        self.assertEqual(self.client.post(base + "/context", headers=self.student,
                                          json={"query": "RC", **self.params}).status_code, 200)
        explanation = self.client.post(base + "/explanation", headers=self.student,
                                       json={"query": "RC", **self.params})
        self.assertEqual(explanation.status_code, 200)
        self.assertEqual(explanation.json()["suspected_cause"], "apparatus")
        self.assertEqual(explanation.json()["next_action"], "Ask the instructor to compare the probe.")
        self.assertEqual(self.calls["diagnostic"], 1)

        first = self.client.post(base + "/outcome", headers=self.student, json=self.params)
        second = self.client.post(base + "/outcome", headers=self.student, json=self.params)
        self.assertEqual(first.json()["status"], "stored")
        self.assertEqual(second.json()["status"], "already_stored")
        saved = self.client.get(base + "/outcome", headers=self.student, params=self.params)
        self.assertEqual(saved.json()["outcome"]["diagnostic_evidence"]["source"], "trusted-ml2")
        listing = self.client.get(base + "/personal-context", headers=self.student,
                                  params=self.params).json()
        self.assertEqual(len(listing["memories"]), 1)
        memory_id = listing["memories"][0]["id"]
        corrected = self.client.patch(base + f"/personal-context/{memory_id}",
                                      headers=self.student, params=self.params,
                                      json={"replacement": "Simulated corrected memory"})
        self.assertEqual(corrected.status_code, 200)
        forgotten = self.client.delete(base + f"/personal-context/{memory_id}",
                                       headers=self.student, params=self.params)
        self.assertEqual(forgotten.status_code, 200)
        self.assertEqual(self.client.get(base + "/personal-context", headers=self.student,
                                         params=self.params).json()["memories"], [])

        queue = self.client.get("/reviews", headers=self.teacher)
        self.assertEqual(len(queue.json()), 1)
        decision = self.client.post(f"/reviews/{self.flag['flag_id']}/decision", headers=self.teacher,
                                    json={"approve": True, "note": "Instructor-approved equipment warning",
                                          "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        self.assertEqual(decision.status_code, 200)
        context = self.client.post(base + "/context", headers=self.student,
                                   json={"query": "RC", **self.params}).json()
        self.assertEqual(context["approved_equipment"][0]["verification"], "instructor_verified")
        repaired = self.client.post("/equipment/scope-3/repair", headers=self.tech,
                                    json={"channel": "CH2", "simulated": True, "note": "Repaired"})
        self.assertEqual(repaired.json()["retired_count"], 1)
        context = self.client.post(base + "/context", headers=self.student,
                                   json={"query": "RC", **self.params}).json()
        self.assertEqual(context["approved_equipment"], [])

    def test_identity_session_and_trusted_diagnostic_boundaries(self):
        request = {"query": "RC", **self.params}
        self.assertEqual(self.client.post("/sessions/s1/explanation", json=request).status_code, 401)
        self.assertEqual(self.client.post("/sessions/s1/explanation", headers=self.teacher,
                                          json=request).status_code, 403)
        self.assertEqual(self.client.post("/sessions/s2/explanation", headers=self.student,
                                          json=request).status_code, 403)
        self.assertEqual(self.client.post("/sessions/s1/explanation", headers=self.student,
                                          json={**request, "diagnostic": {"suspected_cause": "wiring"}}).status_code, 422)
        self.assertEqual(self.client.post("/sessions/s1/outcome", headers=self.student,
                                          json={**self.params, "diagnostic_evidence": {"fake": True}}).status_code, 422)
        self.assertEqual(self.calls, {"diagnostic": 0, "outcome": 0})
        self.assertEqual(self.client.get("/reviews", headers=self.student).status_code, 403)
        self.assertEqual(self.client.get("/sessions/s1/personal-context", headers=self.teacher,
                                         params=self.params).status_code, 403)
        self.assertEqual(self.client.post("/equipment/scope-3/repair", headers=self.student,
                                          json={"channel": "CH2", "simulated": True, "note": "Done"}).status_code, 403)

    def test_factory_requires_security_callbacks(self):
        with self.assertRaises(ValueError):
            create_ml3_app(service_factory=None, resolve_principal=None,
                           authorize_session=None, resolve_diagnostic=None, resolve_outcome=None)
