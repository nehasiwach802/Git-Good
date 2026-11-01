ï»¿# Android / backend API contract 1.1

Owner: ML2/backend; JSON creation, separate MP4 upload, nested event payloads,
`expected_session_version` and `close_session` are confirmed by the user on
2026-11-01. This supersedes the earlier combined multipart/flat-event interface.

## Authentication and endpoints

Send `Authorization: Bearer <Firebase ID token>` for every session operation.
The backend verifies identity and checks session ownership/lab. Android never
supplies trusted UID, role, datapack, reference circuit or diagnosis fields.
Use a UUID `Idempotency-Key` header for creation and video upload; reuse the same
key and identical content for network retries. Keys are scoped per operation.

| Method/path | Content | Result |
|---|---|---|
| GET `/api/v1/experiments` | None | Catalog IDs/versions and review metadata |
| GET `/api/v1/capabilities` | None | Supported reasoning models/analyses |
| POST `/api/v1/sessions` | JSON below | 201 snapshot, `awaiting_image` |
| POST `/api/v1/sessions/{session_id}/image` | Multipart below | 202 snapshot, `extracting` |
| GET `/api/v1/sessions/{session_id}` | None | Current snapshot |
| POST `/api/v1/sessions/{session_id}/events` | Nested JSON event | Updated snapshot; may queue processing |
| GET `/api/v1/sessions/{session_id}/image` | None | Owner-only selected review frame, 404 before extraction |
| DELETE `/api/v1/sessions/{session_id}` | None | 204 local data deletion; separate from closing |

`/health`, `/ready`, `/docs`, and `/openapi.json` are public. `/ready` checks offline
configuration/storage/solver availability and returns 200 or 503. The count of
approved real experiments is informational there; `python -m backend.preflight
--production` additionally requires approved real records. Readiness does not
prove provider accuracy or successful live authentication.

## Create, upload, poll

POST `/api/v1/sessions` with `Content-Type: application/json`:

```json
{
  "experiment_id": "nand-not-example",
  "experiment_version": "1",
  "description": "My output does not change"
}
```

`experiment_version` is optional only when the ID has one configured version.
Description is nonblank and <=2000 characters. This saves a real session with
`session_version: 1`, `state: "awaiting_image"`, `image: null`, `candidate: null`
and no background job. It does not run models.

POST `/api/v1/sessions/{session_id}/image` as `multipart/form-data`:

- `image`: MP4 file with Content-Type `video/mp4`, <=50 MiB. JPEG/PNG inputs are rejected (415).
- Video metadata duration <=60 seconds, decoded input frame <=8.5 megapixels.
- Multipart envelope <=51 MiB; JSON requests <=512 KiB.
- `expected_session_version`: latest integer snapshot version.
- Header `Idempotency-Key`: UUID for this upload operation.

Let the HTTP library set the multipart boundary. The private video source and extraction
job are persisted atomically; upload increments the version. One initial video is
accepted per session. Conflicting or stale uploads return 409. A retried upload
with the identical key/body returns its original response even after extraction
has finished, so GET again afterward. Corrections after upload use review events;
start a new session for a new recording.

The route and file-field retain the historical name `image` for Android compatibility.
Likewise `awaiting_image` and `upload_image` are wire labels for video upload.
ML1 samples up to six frames and selects one for review. Internal JPEGs are decoded
video frames, never accepted user image uploads. GET `/image` returns that selected
review frame. `ml1.media` contains video receipt and frame metadata, without raw
video bytes or private paths. Candidate hashes bind to the selected frame.
No frame-selection event or new video route is introduced. Student confirmation,
ML2 diagnosis and ML3 explanation retain the existing contract.

Poll GET every 1-2 seconds while state is `extracting`, `diagnosing` or `completing`;
back off on errors. Stop polling when awaiting input or closed. Render messages
and structured actions from the snapshot. `session_version` increments for both
student events and background processing; always use a fresh snapshot before a
new action. `candidate_revision` is a separate physical-observation revision.

## Nested event envelope

Every event has exactly these outer fields; event-specific fields go in `payload`:

```json
{
  "event_id": "00000000-0000-4000-8000-000000000001",
  "expected_session_version": 4,
  "type": "confirm_candidate",
  "payload": {
    "candidate_revision": 2,
    "acknowledgement": "reviewed_all_connections_and_board"
  }
}
```

All payloads are typed with unknown fields rejected. `expected_version` and flat
payload fields are rejected on this endpoint. Replay an identical event ID/body
for network retries. A duplicate returns its original response, potentially older
than the latest snapshot. GET after replay. A stale version returns 409; refresh
and have the student reapply the action with a new event ID. Never silently update
a stale confirmation's version/revision.

| type | payload fields |
|---|---|
| `correct_endpoint` | `candidate_revision`, `target`, `hole` or `external_terminal` (one or neither) |
| `replace_candidate` | `candidate_revision`, `candidate` (complete edited ML1 candidate) |
| `set_correspondence` | `component_map`, optional `port_map` |
| `confirm_candidate` | `candidate_revision`, explicit acknowledgement shown above |
| `measurements` | `candidate_revision`, `measurements`, `student_expectations` |
| `source_settings` | `candidate_revision`, `sources` mapping source IDs to finite numeric `{ "dc": 0, "ac": 1 }` in volts |
| `message` | `text`, <=2000 characters |
| `check_result` | `check_id` from current diagnostic, `observation` text |
| `close_session` | Optional `resolved` boolean, default false |
| `retry_extraction` | Empty object, only after failed processing |

Unknown endpoints/alternatives and unknown passive values block confirmation.
The student reviews all parts, wiring omissions, values and board topology. The
model cannot grant confirmation. Corrections increment candidate revision and
clear review/diagnosis. ML1 candidates use schema 0.1 or reviewed external-terminal
0.2. Reference IDs and port/probe/source metadata come from experiment lookup;
reference wiring never enters image extraction. Source settings are reported by
the student, not copied from the ideal circuit.

Digital measurements/expectations are lists of integer binary rows, e.g.
`[{"input":0,"output":1},{"input":1,"output":0}]`; send `student_expectations: []`
when absent. Analog readings use probe IDs, e.g.
`{"probe_id":"output","value":0.707,"unit":"V","convention":"ac_magnitude"}`;
analog expectations are probe-ID -> numeric-value objects. Missing expectations
are `{}` for analog. Messages/check reports do not manufacture readings or edit
the circuit; use structured controls for those actions.

## Closing and state

```json
{
  "event_id": "00000000-0000-4000-8000-000000000002",
  "expected_session_version": 8,
  "type": "close_session",
  "payload": { "resolved": true }
}
```

Close an idle draft or unevaluated session directly to `closed`; no diagnostic
outcome is written. Closing an evaluated session first returns `completing`, runs
ML3 outcome storage, then becomes `closed`. Missing memory is reported explicitly;
uncertain writes need operator reconciliation, never automatic duplicate retries.
`resolved` is a student report, not proof of an apparatus fault. Processing states
reject close/edits with 409; wait for processing to finish. Closed sessions are
immutable except for explicit deletion. DELETE is not a substitute for close.

States: `awaiting_image`, `extracting`, `awaiting_review`, `diagnosing`,
`awaiting_measurement`, `awaiting_check_result`, `completing`, `closed`, `failed`.
Canonical snapshots use `api_version: "1.1"` and `session_version` (not `version`).
Restart preserves queued jobs; interrupted running jobs require explicit handling.

## Errors, ML3 and compatibility

400 malformed/duplicate-key/non-finite JSON; 401 missing/invalid Firebase token;
403 role denied; 404 unknown/unowned session or absent image; 409 stale/busy/closed/
conflicting request; 413 size; 415 invalid image; 422 invalid typed payload;
503 missing/invalid server credentials, Firebase service/OAuth/permission failures,
missing readiness configuration or unavailable optional memory operations;
500 unexpected authentication backend failure. Invalid/expired/revoked tokens
remain 401. Server credentials are validated offline by readiness; live Firebase
permission validation is a separate operator diagnostic, not a health-check call.
Inspect status first: errors use `detail` or validation `error`/`fields`.
Uploads have a 6 MiB total envelope limit; JSON requests/events have 512 KiB.

[Main OpenAPI](../schemas/backend-openapi.json) is generated from these actual
routes. ML3 remains mounted at `/api/v1/ml3` with its
[separate schema](../schemas/backend-ml3-openapi.json). The normal Android flow
gets ML3 explanations automatically through snapshots. Memory is scoped by a
server-owned mapping, and product memory is separate from the build datapack.
Qwen adds optional wording; ML2 owns diagnosis and next actions. Probabilities
are preserved when supplied, otherwise `cause_probabilities: null` with
`probability_status: "not_calibrated"` and ordinal hypothesis support.

Old combined image-upload POSTs `/api/sessions` and `/api/legacy/v1/sessions`
are retired with 410. Historical record GET/event routes remain for compatibility.
Old payload definitions are archived in [BACKEND_API_V1_LEGACY.md](BACKEND_API_V1_LEGACY.md).

Deletion removes private video source, stored frames, session/events/jobs/upload
receipts. Separate ML3 outcomes and Meko memories need their own retention controls.
See [Android video handoff](ANDROID_VIDEO_HANDOFF.md).

Run `python tools/run_checks.py` and `python tools/demo_backend.py`. The demo saves
`outputs/backend/synthetic-transcript.json` using actual ML1/ML2/ML3 interfaces,
injected test identity and synthetic data; no live product/provider calls.

## Grid and wire review extension

API1.1 now supports grid-review-1, discovered via GET /api/v1/capabilities.
Existing endpoints/envelopes remain compatible. New nested event types are
accept_grid, reject_grid, tap_endpoint, add_wire and remove_wire. Read-only preview:
POST /api/v1/sessions/{session_id}/grid/suggest. Payloads, frame/board bindings,
error codes and Android requirements: [grid/wire contract](BACKEND_GRID_API.md).
AUTO_GRID_ENABLED=true enables extraction; no automatic circuit confirmation.
