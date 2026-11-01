"""Four explicit ML 3 operations for an authenticated application backend."""

from knowledge_lifecycle import Principal
from mentor import explain_diagnostic, retrieve_authorized_context


class ML3Service:
    def __init__(self, *, memory, knowledge, outcome_writer, generate=None):
        self.memory = memory
        self.knowledge = knowledge
        self.outcome_writer = outcome_writer
        self.generate = generate

    @staticmethod
    def _student(principal):
        if not isinstance(principal, Principal) or principal.role != "student":
            raise PermissionError("Authenticated student role required")

    def retrieve_context(self, principal, *, session_id, query, equipment_id,
                         channel, simulated, now):
        self._student(principal)
        return retrieve_authorized_context(
            principal, memory=self.memory, knowledge=self.knowledge,
            session_id=session_id, query=query, equipment_id=equipment_id,
            channel=channel, simulated=simulated, now=now)

    def explain_result(self, principal, diagnostic, *, query, equipment_id,
                       channel, simulated, now):
        self._student(principal)
        context = self.retrieve_context(
            principal, session_id=diagnostic.session_id, query=query,
            equipment_id=equipment_id, channel=channel, simulated=simulated, now=now)
        return explain_diagnostic(diagnostic, context=context, generate=self.generate)

    def store_outcome(self, principal, outcome):
        self._student(principal)
        return self.outcome_writer.submit(principal.actor_id, outcome)

    def local_outcome(self, principal, session_id):
        self._student(principal)
        return self.outcome_writer.local_outcome(principal.actor_id, session_id)

    def review_flag(self, principal, *, flag_id, approve, note, now, expires_at=None):
        return self.knowledge.decide(principal, flag_id, approve=approve,
                                     note=note, now=now, expires_at=expires_at)

    def pending_reviews(self, principal):
        return self.knowledge.review_queue(principal)
