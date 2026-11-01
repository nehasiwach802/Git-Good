# Archived backend 1.0 contract

Superseded by BACKEND_API.md. Combined multipart creation and flat events now live only under `/api/legacy/v1/sessions`. This document preserves the earlier payload definitions; its original `/api/v1/sessions` paths are historical, not current.

# Android / backend API contract 1.0

Owner: ML2/backend. This replaces the upload-only prototype for actual sessions.
Sources integrated: ML1 `origin/Abhiram` 07b38aa, ML2 generalized core on the backend branch, ML3 `origin/Manit` c084375. Android remains in its own branch and calls this HTTP API; it does not merge Python into the APK.

## Authentication and endpoints

Every `/api/v1` operation requires `Authorization: Bearer <Firebase ID token>` from the Android Firebase SDK. The backend verifies it against `FIREBASE_PROJECT_ID`; never send a UID, role, datapack ID, reference circuit, or diagnosis as trusted client fields. Instructor/admin roles and lab IDs come from Firebase custom claims. Without a lab claim the server uses its configured DEFAULT_LAB_ID. `/health`, `/ready`, and API documentation are public. `/ready` returns 200 or 503 with offline configuration/storage/solver checks, not a live provider acceptance test.

| Operation | Request | Result |
|---|---|---|
| GET `/api/v1/experiments` | No body | Supported IDs/versions, simulation/approval flags and review metadata (component IDs, ports, probes, source inputs) |
| POST `/api/v1/sessions` | Multipart fields below; UUID `Idempotency-Key` header | 202 session snapshot, usually `extracting` |
| GET `/api/v1/sessions/{session_id}` | No body | Current snapshot; poll every 1-2 seconds during processing, back off on errors |
| POST `/api/v1/sessions/{session_id}/events` | One JSON event | Updated snapshot; queued operations continue in background |
| GET `/api/v1/sessions/{session_id}/image` | No body | Owner-only original image, private/no-store |
| DELETE `/api/v1/sessions/{session_id}` | No body; cannot delete while busy | 204; removes local session, image, events and jobs |

Multipart fields: `experiment_id` (required), `experiment_version` (optional if ID has one version), `description` (required, nonblank, <=2000 characters), `image` (required JPEG/PNG, <=5 MiB and <=20 MP). Android must let its HTTP library set the multipart boundary. Send the image as a file part, not base64 JSON. Reuse the upload idempotency key for network retries of the same upload; conflicting reuse gives 409.

Snapshot fields are defined in [OpenAPI](../schemas/backend-openapi.json). `version` is the session version; `candidate_revision` belongs to the extracted physical observations. They are distinct. `candidate` and `board` use ML1's actual contracts (0.1 hole-only or 0.2 external terminals). `diagnostic` is the ML2 schema 2.0 result. `messages` supplies chat text; `actions` supplies review/measurement/check controls. Always render `error`, `limitations`, `capability_gaps`, `simulated` and memory availability truthfully. Do not turn an unresolved cause into a confirmed fault.

## Events and review

Every event includes `event_id` (new UUID for each intended action) and `expected_version` (latest snapshot version). Network retries must reuse the identical event ID and payload. A duplicate returns the original event response, which may be older than the current snapshot; GET again after replay. 409 means refresh, then ask the student to reapply the action using a new event ID. Do not silently substitute a new revision or version into an old confirmation.

Example:

```json
{
  "type": "confirm_candidate",
  "event_id": "00000000-0000-4000-8000-000000000001",
  "expected_version": 3,
  "candidate_revision": 2,
  "acknowledgement": "reviewed_all_connections_and_board"
}
```

Only send this after the student explicitly reviews all observations, missing parts/wires, component values, and board topology. Unknown endpoints/alternatives and unknown passive values block confirmation. The model cannot grant review. The server clears review after any correction.

| Event type | Additional fields |
|---|---|
| `correct_endpoint` | `candidate_revision`, `target` (ML1 endpoint ID), `hole` or `external_terminal` (one or neither) |
| `replace_candidate` | `candidate_revision`, `candidate` (complete edited ML1 candidate; supports values, added/missing components/wires/ports). Server fixes identity/image/board IDs and clears review. |
| `set_correspondence` | `component_map` (observed component ID -> reference component ID or null), `port_map` (observed port ID -> reference port ID). References remain server-owned. |
| `confirm_candidate` | `candidate_revision`, acknowledgement shown above |
| `measurements` | `candidate_revision`, `measurements`, `student_expectations` |
| `source_settings` | `candidate_revision`, `sources`: source ID -> `{ "dc": 0, "ac": 1 }` in volts. These are student-reported settings, never copied from the ideal reference. |
| `message` | `text`. Records chat and repeats grounded guidance; it does not parse free text into circuit edits or measurements. |
| `check_result` | `check_id` from current `next_check`, `observation` text; records a report, not an invented measurement. |
| `complete` | `resolved` boolean; requires evaluated diagnosis; schedules ML3 outcome storage |
| `retry_extraction` | No additional fields; explicit retry after failed processing. Outcome writes with uncertain status require operator reconciliation. |

Digital readings and expectations are lists of `{ "input": 0, "output": 1 }` integer binary rows, at most two distinct inputs. For digital requests explicitly send `student_expectations: []` when absent. Analog measurements are ML2 probe readings, e.g. `{ "probe_id": "output", "value": 0.707, "unit": "V", "convention": "ac_magnitude" }`; expectations use the existing ML2 contract. See `examples/rc.json`. Reporting a check does not automatically establish a wiring or apparatus fault.

States: `extracting`, `awaiting_review`, `diagnosing`, `awaiting_measurement`, `awaiting_check_result`, `completing`, `completed`, `failed`. Processing states reject concurrent edits. Completed sessions are immutable. A service restart preserves queued jobs; interrupted running jobs are marked explicitly, never silently replayed. Interrupted outcomes are marked for reconciliation.

Responses: 400 malformed/non-finite/duplicate-key JSON; 401 missing/invalid token; 403 role denied; 404 unknown/unowned session; 409 stale/busy/conflicting request; 413 size; 415 invalid image; 422 invalid input; 503 authentication configuration or memory unavailable. Error bodies can use FastAPI `detail` or validation `error`/`fields`; inspect status first. Body limits apply to streamed uploads too (6 MiB envelope; 512 KiB event bodies).

## ML3 and probabilities

User preference: probabilities are the preferred ML3 representation. ML3 preserves ML2-supplied `cause_probabilities` for wiring/concept/apparatus and includes them in grounded text. Current ML2 has no calibrated classifier: its real output is ordinal support. Therefore current integration returns `cause_probabilities: null`, `probability_status: "not_calibrated"`, and `hypothesis_support`. No ordinal-to-percentage conversion is performed. Supplying meaningful probabilities requires a defined scoring/calibration method and held-out labelled faults; Qwen wording does not create diagnostic probabilities.

The actual ML3 service is mounted under `/api/v1/ml3`; its separate schema is [ML3 OpenAPI](../schemas/backend-ml3-openapi.json) and deployed `/api/v1/ml3/docs`. Context/explanation/outcome requests must match the server session's equipment/channel/simulation fields. Diagnostics/outcomes are loaded from the server, never accepted from Android. Outcome POST requires an already completed session and uses ML3's at-most-once ledger. Memory CRUD and instructor equipment review routes enforce existing ML3 authorization. The primary Android flow needs only the session/events routes; it receives explanations automatically.

Personal memory uses an operator-provisioned UID -> datapack mapping, never a phone-provided datapack. Missing memory degrades to a grounded template. Qwen is optional supplementary wording; authoritative diagnosis and next action remain ML2's. Deleting a local session does not erase the separate outcome ledger or personal Meko memories; use ML3 personal-context controls before deleting the session, and define institutional retention before handling real students.

## Acceptance and compatibility

Run `python tools/run_checks.py` (requires test/backend extras and ngspice). `python tools/demo_backend.py` writes an offline synthetic transcript using actual ML1/ML2/ML3 interfaces and injected test authentication, no live product calls. This test-only injection is not an environment authentication bypass.

The old POST `/api/sessions` remains a deprecated, diagnosis-free connectivity smoke endpoint for the existing Android upload screen. It does not create a session for these routes. Android must migrate to `/api/v1/sessions` and authenticate. Its old tests import `backend.smoke`; the real `backend.app` is now integrated.
