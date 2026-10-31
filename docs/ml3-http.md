# ML 3 HTTP integration for the shared backend owner

`ml3_http.create_ml3_app` exposes the ML 3 modules through FastAPI. This is an
adapter to mount inside the team's backend, not a standalone authenticated server.
It deliberately has no default authentication or session store. All handlers are
synchronous, so FastAPI runs blocking Meko/SQLite calls in request worker threads.

## Required application callbacks

The factory requires five callables:

| Callable | Required result |
| --- | --- |
| `service_factory()` | Context manager yielding a new `ML3Service` with its own SQLite connections for that request. Close them on exit. |
| `resolve_principal(request)` | Trusted `Principal(actor_id, lab_id, role)` from the real backend authentication system. Never infer identity from a request body. |
| `authorize_session(principal, session_id, equipment_id, channel, simulated)` | Return literal `True` only if that student owns the session and the lab/equipment/channel/mode match backend records. |
| `resolve_diagnostic(principal, session_id)` | Load a trusted `DiagnosticResult` from ML 2/backend records. Never use a diagnostic object supplied by the phone. |
| `resolve_outcome(principal, session_id)` | Load a trusted `SessionOutcome` with confirmed ML 2 evidence and accepted measurements from backend records. Never use diagnostic evidence supplied by the phone. |

`service_factory` should compose `MekoMemory`, `KnowledgeStore`, and
`OutcomeWriter` with durable database paths under ignored `data/`. The backend
must manage the student-to-personal-datapack mapping and Meko credential. One
SQLite connection per request thread is required. The service object is closed
by the factory after each request. Keep the write ledger across restarts.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /sessions/{id}/context` | Personal recall plus active approved equipment notes. |
| `POST /sessions/{id}/explanation` | Explain the trusted ML 2 diagnostic result. |
| `POST /sessions/{id}/outcome` | Submit the trusted outcome once through the write ledger. |
| `GET /sessions/{id}/outcome` | Read the local exact outcome if a Meko write needs reconciliation. |
| `GET /sessions/{id}/personal-context` | View personal memories with page settings. |
| `PATCH /sessions/{id}/personal-context/{memory_id}` | Correct one owned memory. |
| `DELETE /sessions/{id}/personal-context/{memory_id}` | Forget one owned memory. |
| `GET /reviews` | Instructor's pending flags. |
| `POST /reviews/{flag_id}/decision` | Instructor approves/rejects with note and expiry when approving. |
| `POST /equipment/{equipment_id}/repair` | Technician retires matching flags/warnings. |

Context/explanation requests provide `query`, `equipment_id`, `channel`, and
explicit `simulated` in JSON. The outcome request provides equipment/channel/mode
only; the backend callback supplies the actual outcome. Diagnosis and evidence
fields in request JSON are rejected. Personal-context and local-outcome GET
requests pass equipment/channel/mode as query parameters for authorization.
The backend's session authorization must compare these with stored assignments.
There are no public flag-enqueue routes: trusted backend jobs call
`KnowledgeStore.enqueue` after deterministic aggregation.

Authentication failure is HTTP 401; a forbidden session or role is 403;
malformed or conflicting domain input is 400; body validation is 422; Meko
unavailability during writes is 503. The exact submitted outcome is retained in
the local ledger even if the Meko call fails. If the ledger returns
`needs_reconciliation`, do not automatically resubmit the same session; inspect
the authoritative record and Meko status first.

## Verification

`tests/test_ml3_http.py` runs the entire route flow in process with fake Meko and
temporary SQLite databases, including review, repair, repeat submission,
personal correction/deletion, role restrictions, and rejection of phone-supplied
diagnoses. It makes no product datapack calls. Run it with the repository's
requirements installed:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
```

The team still needs to provide real authentication, authoritative session
records, ML 2 integration, Android calls, deployment configuration, and an
instructor UI. Neither this adapter nor its tests claim those are complete.
