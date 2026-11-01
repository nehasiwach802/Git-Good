# Android grid and wire contract: grid-review-1

Owner: ML2/backend, implementing the user's request on 2026-11-01.
This is an additive extension of API1.1. Existing JSON session creation, MP4 upload
at POST /api/v1/sessions/{id}/image (field image), snapshot fields, nested event
envelope and close_session are preserved. API version stays1.1; discover this
extension through authenticated GET /api/v1/capabilities -> grid_review.contract.
The generated schemas/backend-openapi.json is authoritative for field validation.

## Configuration and snapshots

Set AUTO_GRID_ENABLED=true on the backend and use an experiment with the actual
complete central A-J board profile (10-70 rows, no rails/custom geometry). No
Gemini/YOLO call is needed for grid alignment. Default false preserves old capture
selection. Unsupported/cropped/unclear grids return not_found/unavailable and keep
manual physical-hole correction available. This is experimental assisted geometry,
not independently validated physical hole-ID recognition.

Snapshot fields:

- ml1.grid_proposal: selected-frame geometry, unreviewed provisional hole centers,
  image_sha256, image_size, board_fingerprint, status and bounded quality metadata.
- ml1.media.selected_frame_id: selected returned frame ID, e.g. F1.
- ml1.media.grid_review: server-persisted alignment/printed-label acceptance, when
  accepted. Contains left_top, right_top, accepted_revision and binding metadata.
- ml1.media.grid_rejected: true after rejection; removed after a new acceptance.
- actions[].event_types: available review operations for the current snapshot.

Raw proposal labels_confirmed/reviewed stay false even after acceptance. Use the
server's grid_review record and preview result for accepted physical labels.
Alignment acceptance is never circuit confirmation. GET /image still returns the
selected internal JPEG for display; user input remains MP4 only.

## Common binding and versions

accept_grid, reject_grid, tap_endpoint and add_wire payloads include:

| Field | Value copied from latest snapshot |
|---|---|
| candidate_revision | snapshot.candidate_revision, positive integer |
| frame_id | ml1.media.selected_frame_id, F1 through F6 |
| image_sha256 | snapshot.image.sha256, 64 lowercase hex characters |
| board_fingerprint | ml1.grid_proposal.board_fingerprint, 64 lowercase hex characters |

All mutations use POST /api/v1/sessions/{id}/events and the existing outer fields:

```json
{
  "event_id": "f7429e21-e0aa-48b9-88f1-60c6845593b0",
  "expected_session_version": 3,
  "type": "accept_grid",
  "payload": {
    "candidate_revision": 1,
    "frame_id": "F1",
    "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "board_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "left_top": "A30",
    "right_top": "F1",
    "acknowledgement": "reviewed_grid_alignment_and_printed_labels"
  }
}
```

Hashes/version/labels above are illustrative: use actual snapshot values and the
printed corner labels the student reviewed. Never send a frontend label-map dict.
The two labels describe the top-left printed hole of each detected five-column
strip. Independent row/column reversal and swapped halves are supported.

Every successful mutation returns a normal200 session snapshot and increments
session_version. Candidate-mutating review operations increment candidate_revision,
clear whole-circuit review/diagnosis and obsolete measurements/checks/source settings.
A fresh confirmation is always required. New wire mutations do not call ML3.

Keep event_id and the complete body identical on network retry: the stored original
response is replayed (possibly older than the current state). GET after replay.
Reusing an event ID with a different body returns409. Rejected operations make no
partial changes and do not consume the event ID. On stale versions, refresh and
require deliberate reapplication; never silently reconfirm old observations.

## Mutations

| type | Extra payload fields in addition to common binding |
|---|---|
| accept_grid | left_top, right_top, acknowledgement exactly reviewed_grid_alignment_and_printed_labels |
| reject_grid | None; clears accepted grid mapping and returns to manual review |
| tap_endpoint | target (existing endpoint name, e.g. W1.b or U1.1), xy:[x,y] |
| add_wire | wire_id, a_xy:[x,y], b_xy:[x,y], acknowledgement exactly reviewed_same_physical_wire |

remove_wire requires only candidate_revision and wire_id (no grid binding), so
manual entry/removal works without automatic alignment. It uses the same envelope.
An unknown wire ID, invalid target, duplicate item ID or occupied physical hole is
rejected; nothing is partially persisted. add_wire is an explicit user pairing,
not a detector-based pairing. Its two taps must resolve to separate unoccupied
physical holes. The server computes physical IDs from its accepted label mapping.

After accept_grid, call the preview endpoint for each tap if needed. Then submit
add_wire with both original native pixel coordinates and explicit pairing approval.
Use tap_endpoint to move one end of an existing wire. Existing correct_endpoint
still accepts explicit physical labels, including manual fallback; replace_candidate
remains the existing complete-candidate editing operation. Existing confirm_candidate
with reviewed_all_connections_and_board is final circuit/board/pairing review.

## Read-only hole preview

POST /api/v1/sessions/{id}/grid/suggest with Authorization bearer token and JSON:

```json
{
  "expected_session_version": 4,
  "candidate_revision": 2,
  "frame_id": "F1",
  "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "board_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "xy": [120.5, 240.0]
}
```

Response200 echoes session_version, candidate_revision, frame_id, image_sha256 and
board_fingerprint, plus suggestion with hole, provisional_hole, alternatives,
confidence, reason, source, confirmed, labels_confirmed, image_xy, visible and
snap_distance_pitch. It does not change any session/candidate version or save an
event. No event_id/Idempotency-Key is needed for this read-only request.

Before acceptance hole=null and only provisional_hole may be populated. After
acceptance hole uses verified physical IDs. Ambiguous taps return hole=null with
alternatives. All suggestions remain confirmed=false. No accepted grid means no
physical tap commit; ambiguity on mutation returns422 ambiguous_tap.

Use exact native selected-frame pixels. Invert the actual rendering transform for
letterboxing, zoom/pan and density. Reject margins before sending. Coordinates must
be exactly two finite numbers, not booleans or strings, inside [0,width)x[0,height).
Preview does not reserve a hole: the mutation rechecks binding and occupancy.

## Errors and client behaviour

- 401: missing/invalid Firebase user token; refresh or sign in.
- 403: authenticated principal does not have the required student role.
- 404: no owned session in the authenticated lab (also hides other users' sessions).
- 409: stale_session, stale_candidate, stale_grid_binding, session_busy/closed,
  or idempotency_conflict. GET current snapshot before deliberate resubmission.
- 422: invalid schema, grid_acceptance_required, ambiguous_tap (with alternatives),
  invalid native coordinates, unsupported grid or invalid/occupied endpoint.
- 400: invalid JSON, including NaN/Infinity; 413: oversized body.

Workflow errors use detail.code/message; request-validation errors use
error=invalid_request and fields[]. Do not assume every error has one envelope.
Unknown payload fields are rejected. Existing Firebase503/500 distinctions remain.
Ownership/lab and version checks apply to preview and all mutations. Busy/closed
sessions reject edits. Frame/profile changes invalidate local taps and approval.

## Android scope and test sequence

Use existing SessionApi/SessionRepository and the new typed payloads. Build the
overlay/orientation/explicit two-tap pairing controls described by ML1 in
ANDROID_WIRE_REVIEW_HANDOFF.md. HTTP support is now implemented; Android controls
are still owned by the Android developer. No new Android app is created here.

Test: MP4 upload -> selected frame/grid -> preview provisional hole -> accept
alignment/labels -> preview physical hole -> add paired wire -> move endpoint ->
remove wire -> correct full circuit -> confirm_candidate -> ML2/ML3 -> readings/
close_session. Also test retries, stale bindings, ambiguous taps and another user.

Alternate-frame selection and wire-only exercise completion are not added by this
extension. The wire-hole-practice file is a draft exercise, not an approved backend
catalog entry. Current circuit candidates still require components and ports; do
not advertise a new wire-only experiment without implementing/approving its model.

## Reproduce locally without secrets

```powershell
python tools/demo_backend.py --grid
Get-Content outputs/backend/synthetic-grid-transcript.json
```

This generates a synthetic grid video and simulated student approvals/known circuit
corrections. It exercises actual HTTP handlers and local ML1/ML2/ML3 interfaces,
not live Firebase/Gemini/Qwen/Meko or real-photo accuracy. The existing demo without
--grid continues to work.
