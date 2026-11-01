# Android handoff: automatic grid and touch-based wire review

Date: November 1, 2026. Owner: ML1. Consumer: Android developer, with ML2/backend.

## Goal

Keep the existing video upload and selected-frame conversation flow. Add a review
surface where the grid aligns automatically, the user approves alignment/labels,
and the user taps the two insertion holes belonging to each wire. Detector
suggestions are optional starting points; manual wire entry must work without them.

Expected result: a reviewed list such as `W1: E12 <-> F13`. The system must retain
unknown endpoints and corrections instead of filling in the expected experiment.

## Available implementation and dependencies

- ML1 source is on `Abhiram`, commit `ea67b52`, built on video handoff `393732a`.
- `labvision/autocalibration.py`: automatic central-grid proposal, touch snapping,
  label mapping for independently reversed row directions and swapped strips.
- `process_video(..., auto_grid=True)`: tries sampled frames and prefers a usable
  grid frame. Endpoint detection remains a separately configured optional feature.
- ML1 verification: 106 tests passed. One of six sampled frames from one real
  video aligned; five were rejected. This is a constrained prototype, not broad
  hole-identification accuracy evidence.
- Latest shared ML2 note: `AUTO_GRID_ENABLED` defaults false; the bounded worker
  forwards grid processing and normalizes selected/per-frame metadata. Internal
  `Capture.accept_grid`, `Capture.suggest_hole`, and `Workflow.accept_grid` exist.
  **Public API 1.1 still has no grid-acceptance route/event.** Internal functions
  are not Android HTTP endpoints. See ML2's `docs/ML2_AUTO_GRID_INTEGRATION.md` in
  their checkout for their current consumer contract.

The supplied Android `implementation.md` describes the current client structure
and `git-good-3.onrender.com`. Preserve its configured base URL and existing
Firebase/session transport. This handoff does not establish a fresh live-host test.

## Implement in the existing Android files

Paths below are relative to `app/src/main/java/com/example/gitgood/` in the Android
repository. These are integration suggestions based on the supplied implementation
guide, not edits already made to the Android source.

| File/area | Change |
|---|---|
| `data/backend/BackendModels.kt` | Optional grid/proposal models; tolerate missing metadata and unknown statuses. |
| `data/backend/SessionApi.kt`, `LiveSessionRepository.kt` | Add only the typed operations ML2 actually publishes. Preserve auth, retries and version guards. |
| `viewModel/ConversationViewModel.kt` | Bind local review state to session, selected image hash and candidate revision; submit typed actions. |
| `ConversationUiState.kt` | Selected wire/endpoint, first pending tap, label/alignment approval state, submission errors. |
| `SessionActions.kt` | Inline grid-approval and wire-review controls; keep existing confirmation safeguards. |
| New `WireReviewCanvas.kt` | Frame, grid, endpoint suggestions, selected endpoints, zoom/pan and touch handling. |
| `data/model/Experiment.kt` | Add Wire Connections only with the corresponding backend catalog support. The current menu explicitly resolves five choices. |

## Screen flow

1. Show upload/processing through the existing MP4 workflow.
2. Fetch and display the authenticated selected JPEG using the current frame code.
3. If a grid exists, overlay its central hole centers. Ask: "Do the dots line up
   with the holes?" Include a clear retry/fallback action if they do not.
4. Establish printed label orientation using the top-left hole of each five-column
   strip, unless ML2 provides a previously verified label convention for this
   capture. Highlight those two locations while asking. These are two label
   choices, not four manually positioned calibration anchors.
5. Submit approval through the ML2-published operation, then wait for its accepted
   snapshot. Enable physical-hole editing only for that accepted frame/profile.
6. Offer Add wire. First tap selects end A, second tap selects end B. Show both
   markers and an editable pair row. The user explicitly says these ends belong to
   the same physical wire; do not automatically pair nearest endpoints.
7. Allow selecting an existing wire/end to change its hole, deleting a wire,
   canceling an unfinished pair, and undoing local unsent edits. Deployed mutation
   support must be agreed with ML2 before enabling server-side operations.
8. Show the complete wire list and final review acknowledgement. Persist and
   confirm the current revision through the existing review flow.

Use distinct marker styles for grid holes, unreviewed model proposals, selected
endpoints and unresolved endpoints. A line connecting two selected endpoints is
only a diagram of their pairing; it is not the detected physical wire path.

## Data Android should consume

ML1 library output places the selected proposal at `ml1.grid_proposal`; ML2 owns
the final public snapshot representation and may normalize/filter fields. Confirm
the deployed shape with ML2 before finalizing serialization.

| Field | Meaning |
|---|---|
| `schema_version` | `ml1-grid-proposal-1` in raw ML1 output. |
| `status` | `needs_orientation_review`, `not_found`; video wrapper can return `unavailable`. |
| `image_sha256`, `image_size` | Exact selected JPEG identity and native decoded width/height. |
| `board_fingerprint` | Board geometry identity; changes invalidate mapping. |
| `holes` | Provisional hole IDs mapped to `[x, y]` centers in native frame pixels. |
| `labels_confirmed`, `reviewed` | False in raw ML1 output. Alignment does not confirm a circuit. |
| `quality`, `reason` | Geometric fit diagnostics and fallback explanation. Do not present as model accuracy. |

Raw endpoint proposals live in `ml1.endpoint_detection` with status
`unreviewed_region_proposals`, target `wire_end_region`, and nested
`videos[].frames[]` containing `sha256`, `image_size`, `proposals[]`. Each proposal
has `id`, `box: [x1,y1,x2,y2]`, `score`, and unconfirmed/unknown hole information.
Only draw the entry matching the displayed frame's hash and dimensions. A box
center can miss the actual insertion hole; let the user correct it. Never derive
wire count by halving the number of endpoint proposals.

## Coordinates, zoom and snapping

Store endpoint selections in native frame coordinates, not Compose display pixels.
Render the image, hole markers, boxes and wire lines with the same transform.

For a fitted image without rotation:

```text
fitScale = min(viewWidth / imageWidth, viewHeight / imageHeight)
offsetX = (viewWidth  - fitScale * imageWidth)  / 2
offsetY = (viewHeight - fitScale * imageHeight) / 2

viewX = offsetX + panX + fitScale * zoom * imageX
viewY = offsetY + panY + fitScale * zoom * imageY

imageX = (touchX - offsetX - panX) / (fitScale * zoom)
imageY = (touchY - offsetY - panY) / (fitScale * zoom)
```

These formulas assume zoom about the image origin. If using centroid-based zoom
or a Compose matrix, invert the **actual rendering matrix** instead. Density units
must be consistent: convert touch/layout coordinates to the same canvas-pixel space.
Reject taps outside `[0,width) x [0,height)` after inversion. Treat drags as pan,
not endpoint taps; zooming must not change saved native endpoint coordinates.

ML1 `suggest_hole` snaps in board-pitch coordinates, with a conservative radius and
ambiguity margin. Use the ML2-published suggestion/commit mechanism. If local
highlighting is needed for responsiveness, it is provisional; backend validation
must determine the persisted hole. When two holes are ambiguous, show choices or
ask the user to zoom in instead of silently selecting one.

## Label orientation

Printed numbering can run in opposite directions on the two strips. Geometry
alone cannot read those labels. For example `left_top=A63`, `right_top=F1` is a
possible mapping, not a verified fact for every board. ML2 derives and persists the
mapping from explicit accepted corner labels and ownership/version checks.

Do not send an arbitrary frontend label-map dictionary as proof of verification.
Do not turn raw proposal `labels_confirmed` on locally and treat that as server
acceptance. After mapping, display physical hole IDs rather than provisional IDs.
Outer rails are outside this prototype; taps there need an unsupported-region
message or an explicit manual workflow approved by ML2.

## API coordination checklist for ML2

Before enabling submission, obtain the exact event names, payload schemas,
response fields and error behavior for:

- Accepting/rejecting grid alignment and printed-corner orientation.
- Suggesting a hole from a frame-bound pixel tap, if server-side snapping is used.
- Creating/removing wires and persisting explicit endpoint pairing.
- Retrying/selecting a different frame, if alternate-frame controls are supported.
- Completing a wire-only exercise without measurements or SPICE requirements.

These operations are required capabilities, **not invented event names**. Preserve
the existing JSON event envelope with `event_id`, `expected_session_version`,
`type`, `payload` once ML2 publishes the types. Candidate edits must bind the
current candidate revision; grid/touch operations must also bind selected frame
and board identity as required by that public schema.

Existing `correct_endpoint` supports physical-hole corrections. Existing
`replace_candidate` may support structural edits, but Android must confirm ML2's
validation and pairing requirements instead of treating it as unrestricted access.
Existing `confirm_candidate` is final circuit review, not grid approval.

Keep operation UUIDs stable on retry. Disable duplicate submissions. On conflict,
fetch the current snapshot and require fresh review where applicable. Never carry
unsent wire taps across a changed frame, board, account or candidate revision.

## States and fallback behavior

| Situation | UI behavior |
|---|---|
| No grid field / feature disabled | Existing manual hole entry remains available. |
| `not_found` / `unavailable` | Explain alignment failed; offer the supported retry/manual path. |
| `needs_orientation_review` | Draw provisional grid; request alignment and label approval. |
| Grid accepted by backend | Enable tap-based physical-hole entry for that frame. |
| Detector disabled/unavailable or misses endpoints | User can still add every wire manually. |
| Hidden/unclear endpoint | Keep unknown; request a better view rather than guessing. |
| Pending server operation | Disable affected edits and show progress. |
| Changed selected frame or board | Clear pending taps, approval and stale overlays. |
| Public acceptance API not yet deployed | Build/preview UI locally; keep submission disabled with an honest status. |

## Acceptance checks

- Grid/markers stay aligned when fitting, zooming and panning the selected frame.
- Taps in letterboxing do nothing; midpoint taps remain ambiguous.
- Two taps can create one explicitly paired wire, then edit/delete it using the
  agreed backend contract. Marker movement does not invent a new wire silently.
- Opposite row directions display the verified physical IDs on each strip.
- Changing one endpoint from F12 to F13 persists that exact correction.
- A stale revision/frame cannot be confirmed; refresh invalidates stale local work.
- Failed calibration and missing detector proposals both have usable fallback UI.
- Final confirmation remains an explicit user action and is revision-bound.
- Wire-only sessions do not display irrelevant resistor values or voltage readings.

Related ML1 documents: `AUTO_GRID_HANDOFF.md`, `VIDEO_PROCESSOR_HANDOFF.md`,
`UPLOAD_DETECTOR_INTEGRATION.md`, and `WIRE_HOLE_PRACTICE.md` in this directory.
