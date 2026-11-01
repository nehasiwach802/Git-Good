> Backend update: public grid-review-1 is now implemented through the existing
> event endpoint plus /grid/suggest. The earlier internal-only boundary below is
> historical; follow [BACKEND_GRID_API.md](BACKEND_GRID_API.md) for Android payloads.
> Android still owns the overlay, coordinate transforms and review controls.

# ML1 automatic-grid handoff integrated into ML2

Source owner: ML1/Codex, origin/Abhiram ea67b52, docs/AUTO_GRID_HANDOFF.md.
Consumer owner: ML2/backend Codex, following the user's integration request.

## What runs now

Set AUTO_GRID_ENABLED=true in the backend environment to opt into ML1 geometry.
It works with VISION_ENABLED=false and does not require a trained detector or cloud
inference. Default false preserves existing selection behaviour. The configured
experiment board must match the actual complete central A-J grid (10-70 rows);
rails/custom geometry, partial boards and mismatched row counts fall back to manual
entry. A 30-row catalog profile must never be used for a 63-row physical board.

The existing killable video worker forwards auto_grid to ML1, which prefers the
sharpest supported grid frame. ML2 validates/sanitizes each frame's optional
proposal, persists it in private frame metadata and ml1.media.frames, and exposes
the selected one as ml1.grid_proposal. No raw bytes/private paths are in metadata.
Older records without proposals remain readable. Bad proposals do not destroy the
session: they report unavailable and leave manual review available.

Validation covers image hash/native size, board fingerprint, complete hole set,
finite in-frame centers, forward homography/invertibility/coordinate consistency,
and bounded fit-quality values. The inverse is rebuilt from the checked forward
matrix. Human anchors/checks and review flags are never trusted from auto-fit
metadata. Fit residuals are geometric evidence, not physical hole-ID accuracy.

## ML2 operations and persistence

These are trusted internal Python operations, not new Android routes/events:

```python
capture = capture.accept_grid(
    expected_revision,
    image_sha256=selected_frame_sha,
    left_top="A63", right_top="F1",  # illustrative; student must verify these
    acknowledgement="reviewed_grid_alignment_and_printed_labels",
)
suggestion = capture.suggest_hole(
    capture.candidate["revision"],
    image_sha256=selected_frame_sha,
    xy=[native_x, native_y],
)
```

Before acceptance, suggest_hole returns provisional_hole only, with hole=null.
Acceptance derives the label map server-side from the two printed strip-corner
labels. Each strip can have independent row direction, mirrored columns or swapped
halves. It increments candidate revision, resets circuit review, and stores a
frame/board/proposal-bound grid_review in media. It never alters existing hole
assignments, pairs wires, or grants manual-calibration checks/circuit confirmation.
Ambiguous taps remain unknown; all suggested endpoints have confirmed=false.
Touches must be selected-frame native pixels, never video or screen coordinates.
Nonfinite, boolean, negative and outside-image coordinates are rejected.

Workflow.accept_grid provides an internal persistence coordinator: authenticate
owner/lab/student role, check session and candidate versions and editable state,
restore private assets, accept explicitly, then compare-and-swap in a transaction.
It persists the revised capture and grid_review and clears old diagnosis/readings/
checks/source settings. Concurrent changes reject with409; callers refresh state.
It is not an idempotent HTTP event implementation and is not mounted publicly.
Capture.restore revalidates geometry and acceptance binding. Frame changes remove
acceptance/calibration and invalidate circuit review; stale proposals cannot snap.

## Android and ML3 boundaries

The agreed API1.1 upload route, MP4 image-field payload, nested event envelope,
expected_session_version, close_session and state labels remain compatible.
Public grid-review-1 now adds typed accept_grid, reject_grid, tap_endpoint,
add_wire and remove_wire events on the existing event route, and a read-only
POST /grid/suggest preview. See BACKEND_GRID_API.md for exact schemas and errors.
No existing required fields are changed. Existing correct_endpoint still supports
explicit physical-hole entry without automatic alignment. Never submit provisional
labels as physical corrections. Wire pairing remains explicit student input.

Android owns the overlay, native-pixel letterbox/zoom/pan inversion, printed-label
approval and two-tap pairing controls. Backend HTTP support is implemented; actual
Android controls/device validation remain separate work. Until those screens are
connected, the existing manual physical-hole editing flow remains available.
Enabling AUTO_GRID_ENABLED alone does not implement the Android UI.

ML3 receives the existing diagnostic only. Geometry, grid acceptance, frames and
raw video never become required ML3 fields. A complete diagnostic-equality test
covers a reviewed circuit with automatic-grid acceptance.

## Verification

Run python tools/run_checks.py for the no-skips release suite. Focused tests:
python -m unittest discover -s tests -p test_grid_pipeline.py -v

Tests include synthetic known-coordinate geometry, opposite strip directions,
malformed/unbound proposals, ambiguous/margin taps, revision/frame invalidation,
restore/tampering, owner/lab/role checks, an actual concurrent session change,
real MP4 worker decoding and unchanged ML3 results. These do not establish broad
real-board extraction accuracy or a working Android overlay.
