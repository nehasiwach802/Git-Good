"""Small, transport-independent Meko adapter. No network calls on import."""

from dataclasses import asdict, dataclass
import json
import hashlib
from typing import Any, Callable, Mapping
from uuid import UUID


class MemoryServiceError(RuntimeError):
    """The memory operation failed; callers must not pretend it succeeded."""


@dataclass(frozen=True)
class SessionOutcome:
    session_id: str
    experiment_id: str
    equipment_id: str
    equipment_channel: str
    connections_confirmed: bool
    measurements: tuple[dict[str, Any], ...]
    diagnostic_evidence: dict[str, Any]
    checks_performed: tuple[str, ...]
    resolved: bool
    simulated: bool

    def __post_init__(self):
        for name in ("session_id", "experiment_id", "equipment_id", "equipment_channel"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        for name in ("connections_confirmed", "resolved", "simulated"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(self.diagnostic_evidence, dict):
            raise ValueError("diagnostic_evidence must be an object from ML 2")
        for reading in self.measurements:
            if not isinstance(reading, dict) or not {"node", "value", "unit"} <= reading.keys():
                raise ValueError("Each measurement needs node, value, and unit")
            if not all(isinstance(reading[k], str) and reading[k].strip() for k in ("node", "unit")):
                raise ValueError("Measurement node and unit must be nonempty strings")
            if type(reading["value"]) not in (int, float):
                raise ValueError("Measurement value must be numeric")
        if not all(isinstance(check, str) and check.strip() for check in self.checks_performed):
            raise ValueError("Checks must be nonempty strings")
        # Reject NaN, infinity, and values that cannot be sent as JSON.
        json.dumps(asdict(self), allow_nan=False)


class MekoMemory:
    """Use a trusted backend mapping, never a datapack ID supplied by a student.

    call_tool(name, arguments) must invoke the authenticated Meko MCP tool and
    return its decoded JSON response or MCP result envelope. The caller owns
    authentication, timeouts, and the transport connection.
    """

    def __init__(self, call_tool: Callable, student_datapacks: Mapping[str, str],
                 build_datapack_id: str):
        self._call_tool = call_tool
        self._scopes = dict(student_datapacks)
        if not build_datapack_id.strip():
            raise ValueError("The build datapack ID is required as an exclusion")
        values = list(self._scopes.values())
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("Every student needs an explicit datapack")
        if build_datapack_id in values:
            raise ValueError("Product memory must not use the build datapack")
        if len(set(values)) != len(values):
            raise ValueError("Students must not share personal-memory datapacks")

    def _call(self, name, **arguments):
        try:
            result = self._call_tool(name, arguments)
            if isinstance(result, dict) and result.get("isError"):
                raise MemoryServiceError("Meko reported a tool error")
            if isinstance(result, dict) and result.get("structuredContent") is not None:
                result = result["structuredContent"]
            elif isinstance(result, dict) and "content" in result:
                result = json.loads(next(item["text"] for item in result["content"]
                                         if item.get("type") == "text"))
            if isinstance(result, dict) and "result" in result:
                result = result["result"]
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict) or result.get("error"):
                raise MemoryServiceError("Meko returned an invalid or failed response")
            return result
        except MemoryServiceError:
            raise
        except Exception:
            # Do not include credentials, request payloads, or remote error text.
            raise MemoryServiceError(f"Meko {name} failed") from None

    def _scope(self, student_id):
        try:
            return self._scopes[student_id]
        except KeyError:
            raise ValueError("Student has no configured personal-memory scope") from None

    def start_session(self, student_id: str, session_id: str) -> str:
        datapack_id = self._scope(student_id)
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a nonempty string")
        # A client-provided session name must not reconnect another student's trace.
        scoped_session = hashlib.sha256(
            json.dumps([datapack_id, session_id]).encode("utf-8")).hexdigest()
        result = self._call("conversation_create", datapack_id=datapack_id,
                            agent_id="lab_mentor", session_id=scoped_session,
                            title="Lab session")
        conversation_id = result.get("id")
        if not isinstance(conversation_id, str) or not conversation_id:
            raise MemoryServiceError("Meko did not return a conversation ID")
        return conversation_id

    def recall(self, student_id: str, session_id: str, query: str) -> dict:
        datapack_id = self._scope(student_id)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Recall query must be nonempty")
        conversation_id = self.start_session(student_id, session_id)
        result = self._call("context_search", datapack_id=datapack_id,
                            agent_id="lab_mentor", conversation_id=conversation_id,
                            query=query, limit=5, force_source="memory")
        if not isinstance(result.get("results"), dict):
            raise MemoryServiceError("Meko returned malformed recall results")
        return result["results"]

    def store_outcome(self, student_id: str, outcome: SessionOutcome) -> dict:
        # Revalidate mutable nested fields before making any remote call.
        outcome = SessionOutcome(**asdict(outcome))
        datapack_id = self._scope(student_id)
        conversation_id = self.start_session(student_id, outcome.session_id)
        return self._call("memory_add", datapack_id=datapack_id,
                          agent_id="lab_mentor", conversation_id=conversation_id,
                          text=json.dumps({"kind": "session_outcome", **asdict(outcome)},
                                          allow_nan=False))

    def view_context(self, student_id: str, session_id: str, *, page: int = 1,
                     page_size: int = 20) -> dict:
        """List one page of personal memories, including IDs used by controls."""
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        scope = self._scope(student_id)
        conversation_id = self.start_session(student_id, session_id)
        result = self._call("memory_get_all", datapack_id=scope,
                            conversation_id=conversation_id, agent_id="lab_mentor",
                            page=page, page_size=page_size, promoted=False)
        if not isinstance(result.get("memories"), list):
            raise MemoryServiceError("Meko returned malformed memory listing")
        # The listing API returns text as `data`; search returns it as `memory`.
        # Expose a consistent field without removing the provider's original data.
        rows = []
        for row in result["memories"]:
            if not isinstance(row, dict):
                raise MemoryServiceError("Meko returned a malformed memory row")
            if "memory" not in row and isinstance(row.get("data"), str):
                row = {**row, "memory": row["data"]}
            rows.append(row)
        result = {**result, "memories": rows}
        total_pages = result.get("total_pages")
        if type(total_pages) is not int or total_pages < 0:
            raise MemoryServiceError("Meko returned malformed pagination")
        return result

    def _owned_memory(self, student_id, session_id, memory_id):
        """Resolve an ID inside this student's scope before update/delete."""
        try:
            memory_id = str(UUID(memory_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("memory_id must be a UUID returned by view_context") from None
        page = 1
        while True:
            result = self.view_context(student_id, session_id, page=page, page_size=100)
            if any(row.get("id") == memory_id for row in result["memories"]
                   if isinstance(row, dict)):
                return memory_id
            if page >= result["total_pages"]:
                raise ValueError("Memory is not present in this student's context")
            page += 1

    def correct_context(self, student_id: str, session_id: str,
                        memory_id: str, replacement: str) -> dict:
        """Replace an existing personal memory, not the raw session evidence."""
        if not isinstance(replacement, str) or not replacement.strip():
            raise ValueError("replacement must be nonempty")
        memory_id = self._owned_memory(student_id, session_id, memory_id)
        return self._call("memory_update", datapack_id=self._scope(student_id),
                          conversation_id=self.start_session(student_id, session_id),
                          agent_id="lab_mentor", memory_id=memory_id, text=replacement)

    def forget_context(self, student_id: str, session_id: str, memory_id: str) -> dict:
        """Delete one personal memory. Does not erase logs or session records."""
        memory_id = self._owned_memory(student_id, session_id, memory_id)
        return self._call("memory_delete_by_id", datapack_id=self._scope(student_id),
                          conversation_id=self.start_session(student_id, session_id),
                          agent_id="lab_mentor", memory_id=memory_id)
