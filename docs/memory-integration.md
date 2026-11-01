# Responsibility 1: personal memory integration

This module covers recall, session-outcome submission, and view/correct/forget
controls for personal memories. Equipment aggregation and instructor-approved
shared knowledge belong to later responsibilities.

## Run without credentials

Python 3.11+ is needed for the live transport. Offline adapter tests require no
external packages and never contact product datapacks:

```powershell
py -3 demo_memory.py
py -3 -m unittest discover -s tests -v
```

The demo uses simulated students, measurements, and a nonpersistent fake. It shows
recall before/after outcome storage, isolation, viewing, correction, and forgetting.
Fake storage is exact JSON; real Meko extracts semantic memories and may return
multiple memory rows or no new rows for an outcome. The fake is not a claim about
Meko's extraction quality, indexing delay, or live availability.

## Connect from the application backend

Install `requirements.txt` into a project virtual environment. Configure
`MEKO_MCP_URL` to the actual HTTPS Streamable HTTP endpoint supplied by Meko,
and `MEKO_API_TOKEN` to a valid backend bearer credential. This code does not
guess an endpoint, load credentials from Codex, or implement an OAuth login.
Never commit credentials or put them in the Android app.

```python
from lab_memory import MekoMemory
from meko_transport import MekoTransport

# Resolve these IDs in trusted backend configuration, not request payloads.
memory = MekoMemory(
    MekoTransport.from_env(),
    student_datapacks={"authenticated-student-id": "dedicated-personal-datapack-id"},
    build_datapack_id="actual-build-datapack-id",
)
context = memory.recall("authenticated-student-id", "session-id", "RC filter earlier checks")
```

No network activity occurs until an operation is invoked. The transport uses the
official MCP Python SDK's Streamable HTTP client, initializes the MCP session,
sends bearer authentication, applies a whole-call timeout, and converts SDK
responses into adapter-compatible dictionaries. It opens a connection per tool
call, with no application-level write retries. This synchronous interface must
run in a worker thread if used inside an asynchronous web server.

Official transport reference:
https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/client.md

## Interface for Android and ML 2 integration

- `recall(student_id, session_id, query)` retrieves only the personal-memory
  source. Call before constructing guidance. An empty result is different from a
  `MemoryServiceError`; the UI should show that memory is unavailable on failure.
- `store_outcome(student_id, SessionOutcome(...))` submits ML 2 evidence and
  measurements with units. `simulated` is required. Save the exact session in
  an authoritative backend database separately; Meko is not an exact JSON store.
  Do not automatically retry writes until a deduplication policy is implemented.
- `view_context(student_id, session_id, page=1, page_size=20)` lists one page
  under `memories`, plus pagination metadata. Use the returned UUIDs for controls.
  The provider listing uses `data` for text while search uses `memory`. The
  adapter adds a canonical `memory` field to listing rows with string `data`,
  preserving the original field and any existing `memory` value. Acceptance
  compares the canonical text exactly; it does not skip correction verification.
- `correct_context(student_id, session_id, memory_id, replacement)` replaces
  one personal memory. It does not alter historical measurements or diagnoses.
- `forget_context(student_id, session_id, memory_id)` deletes that memory row.
  It does not promise erasure of conversation traces, search logs, backups, or
  future authoritative records. Whole-account erasure is a separate feature.

Correct/forget first verify the UUID is in the student's own personal-memory
listing, following pages as needed. The backend must authenticate the student;
the library itself is not an HTTP authentication layer. Dedicated datapacks must
contain only personal memories written with `agent_id="lab_mentor"`; do not
promote these memories into shared knowledge. Server-side datapack permissions
remain essential. `agent_id` alone is not a privacy boundary.

Session names are hashed with their datapack scope before conversation creation,
so two students using the same session label cannot reconnect the same trace.
Recall excludes conversation/knowledge-base sources so an older conversation
does not reintroduce corrected or deleted personal memory through those sources.
The provider still controls index consistency and deletion propagation.

## Verification boundary

The coding agent may access only `gitgood-build`, never product datapacks.
Consequently, product live acceptance must be performed by the application owner:
configure a dedicated synthetic-data scope, store a simulated outcome, list its
extracted memories, correct one, check subsequent recall, delete it, and check
again after indexing settles. Confirm isolation with another dedicated scope.
Endpoint authentication and live behavior are not certified by offline tests.

Neither this module nor the transport sends every chat prompt to Meko implicitly.
The application must explicitly invoke its memory operations.

## Application-owner live acceptance

Run these yourself from the repository root (the coding agent must not execute
the live check):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_live_memory.ps1
```

The launcher asks for the actual Meko HTTPS Streamable HTTP endpoint, two empty
synthetic-data datapack UUIDs, and a bearer token entered with hidden input.
Create those two dedicated datapacks in your Meko account first; do not use
`gitgood-build`, real student scopes, or scopes used by a running application.
The endpoint and backend bearer credential must be supplied by your Meko setup;
the Codex connector's credentials are not automatically available to Python.
The launcher restores its process environment afterward and saves no credential file.

`live_memory_check.py` checks authentication/listing, initial recall, submission
of a simulated outcome, extraction and recall, second-student isolation, correction,
and deletion. It waits up to 60 seconds per indexing condition rather than treating
an acknowledgement as proof of successful recall. It refuses pre-existing regular
memories, and attempts to clean up synthetic memories even on failure. No blanket
delete operation is used; provider traces may remain. Empty extraction, unexpected
response shapes, cleanup failures, and timeouts produce failure instead of success.
Do not rerun after failed cleanup until you have inspected the test scope.

Successful output ends with `ALL CHECKS PASSED for the configured synthetic scopes`.
This verifies application-level routing in those scopes, not every server-side
permission configuration or a whole-account erasure guarantee. Share the PASS/FAIL
status for troubleshooting, never the token or raw personal-memory content.
