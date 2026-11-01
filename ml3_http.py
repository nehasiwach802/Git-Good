"""HTTP adapter for ML 3 operations; authentication is injected by the backend."""

from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from knowledge_lifecycle import Principal
from lab_memory import MemoryServiceError, SessionOutcome
from mentor import DiagnosticResult


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContextBody(StrictBody):
    query: str = Field(min_length=1)
    equipment_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    simulated: bool


class OutcomeRequest(StrictBody):
    equipment_id: str
    channel: str
    simulated: bool


class CorrectionBody(StrictBody):
    replacement: str = Field(min_length=1)


class DecisionBody(StrictBody):
    approve: bool
    note: str = Field(min_length=1)
    expires_at: datetime | None = None


class RepairBody(StrictBody):
    channel: str | None = None
    simulated: bool
    note: str = Field(min_length=1)


def create_ml3_app(*, service_factory: Callable, resolve_principal: Callable,
                   authorize_session: Callable, resolve_diagnostic: Callable,
                   resolve_outcome: Callable) -> FastAPI:
    """All callbacks are mandatory and must enforce real backend permissions.

    resolve_principal(request) -> trusted Principal or raises PermissionError.
    authorize_session(principal, session_id, equipment_id, channel, simulated)
    must check student ownership, lab assignment, and equipment/session binding.
    resolve_diagnostic / resolve_outcome load trusted results from backend records;
    never use diagnosis or evidence claimed by a phone request. service_factory()
    returns a context manager that creates/owns connections in the request thread.
    Handlers are synchronous so blocking Meko/SQLite calls run in worker threads.
    """
    if not all(callable(value) for value in (service_factory, resolve_principal,
                                            authorize_session, resolve_diagnostic, resolve_outcome)):
        raise ValueError("All backend security and data callbacks are required")
    app = FastAPI(title="AI Lab Mentor ML3 API", version="0.1")

    def identity(request):
        try:
            principal = resolve_principal(request)
            if not isinstance(principal, Principal):
                raise PermissionError("Authentication required")
            return principal
        except PermissionError:
            raise HTTPException(401, "Authentication required") from None

    def allowed(request, session_id, equipment_id, channel, simulated):
        principal = identity(request)
        if principal.role != "student":
            raise HTTPException(403, "Student role required")
        try:
            if authorize_session(principal, session_id, equipment_id, channel, simulated) is not True:
                raise PermissionError("Session access denied")
        except PermissionError:
            raise HTTPException(403, "Session access denied") from None
        return principal

    def execute(action):
        try:
            with service_factory() as service:
                return action(service)
        except PermissionError:
            raise HTTPException(403, "Not authorized") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except MemoryServiceError:
            raise HTTPException(503, "Memory unavailable; local outcome retained when submitted") from None

    @app.post("/sessions/{session_id}/context")
    def context(session_id: str, body: ContextBody, request: Request):
        principal = allowed(request, session_id, body.equipment_id, body.channel, body.simulated)
        return execute(lambda service: service.retrieve_context(principal, session_id=session_id,
            query=body.query, equipment_id=body.equipment_id, channel=body.channel,
            simulated=body.simulated, now=datetime.now(timezone.utc)))

    @app.post("/sessions/{session_id}/explanation")
    def explanation(session_id: str, body: ContextBody, request: Request):
        principal = allowed(request, session_id, body.equipment_id, body.channel, body.simulated)
        def run(service):
            result = resolve_diagnostic(principal, session_id)
            if not isinstance(result, DiagnosticResult) or result.session_id != session_id:
                raise ValueError("Backend returned an invalid diagnostic result")
            return service.explain_result(principal, result, query=body.query,
                equipment_id=body.equipment_id, channel=body.channel,
                simulated=body.simulated, now=datetime.now(timezone.utc))
        return execute(run)

    @app.post("/sessions/{session_id}/outcome")
    def outcome(session_id: str, body: OutcomeRequest, request: Request):
        principal = allowed(request, session_id, body.equipment_id,
                            body.channel, body.simulated)
        def run(service):
            stored = resolve_outcome(principal, session_id)
            if (not isinstance(stored, SessionOutcome) or stored.session_id != session_id or
                stored.equipment_id != body.equipment_id or
                stored.equipment_channel != body.channel or stored.simulated != body.simulated):
                raise ValueError("Backend returned an outcome for another session or equipment")
            return service.store_outcome(principal, stored)
        return execute(run)

    @app.get("/sessions/{session_id}/outcome")
    def local_outcome(session_id: str, request: Request, equipment_id: str,
                      channel: str, simulated: bool):
        principal = allowed(request, session_id, equipment_id, channel, simulated)
        return execute(lambda service: service.local_outcome(principal, session_id))

    @app.get("/sessions/{session_id}/personal-context")
    def personal_context(session_id: str, request: Request, equipment_id: str,
                         channel: str, simulated: bool, page: int = 1, page_size: int = 20):
        principal = allowed(request, session_id, equipment_id, channel, simulated)
        return execute(lambda service: service.memory.view_context(principal.actor_id, session_id,
                                                           page=page, page_size=page_size))

    @app.patch("/sessions/{session_id}/personal-context/{memory_id}")
    def correct(session_id: str, memory_id: str, body: CorrectionBody, request: Request,
                equipment_id: str, channel: str, simulated: bool):
        principal = allowed(request, session_id, equipment_id, channel, simulated)
        return execute(lambda service: service.memory.correct_context(principal.actor_id, session_id,
                                                              memory_id, body.replacement))

    @app.delete("/sessions/{session_id}/personal-context/{memory_id}")
    def forget(session_id: str, memory_id: str, request: Request,
               equipment_id: str, channel: str, simulated: bool):
        principal = allowed(request, session_id, equipment_id, channel, simulated)
        return execute(lambda service: service.memory.forget_context(principal.actor_id, session_id, memory_id))

    @app.get("/reviews")
    def reviews(request: Request):
        return execute(lambda service: service.pending_reviews(identity(request)))

    @app.post("/reviews/{flag_id}/decision")
    def decision(flag_id: str, body: DecisionBody, request: Request):
        return execute(lambda service: service.review_flag(identity(request), flag_id=flag_id,
            approve=body.approve, note=body.note, now=datetime.now(timezone.utc),
            expires_at=body.expires_at))

    @app.post("/equipment/{equipment_id}/repair")
    def repair(equipment_id: str, body: RepairBody, request: Request):
        return execute(lambda service: {"retired_count": service.knowledge.mark_repaired(
            identity(request), equipment_id, channel=body.channel, simulated=body.simulated,
            note=body.note, now=datetime.now(timezone.utc))})

    return app
