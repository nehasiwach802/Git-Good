# ML2 image/video pipeline

Implemented on `tanu` using ML1 `origin/Abhiram` commit393732a. The backend branch
and ML3 code are not changed by this work. Backend planning notes from before the
branch switch remain in `stash@{0}`; no user work was discarded.

## Boundary and flow

Image or video -> ML1 extraction -> ML2 Capture -> explicit student correction and
review -> existing schema2.0 reasoning -> unchanged diagnostic result -> ML3.

Media bytes, overlays, frames, calibration and asset metadata stay on the ML2 /
backend side. They are not added to the diagnostic object sent to ML3. A regression
test compares the entire selected-frame diagnostic against the existing non-video
request for the same reviewed circuit, not only its field names. No ML3 model,
memory code, HTTP routes or probabilities were modified.

This branch supplies the callable media pipeline, asset persistence/restore and
worker-side session update. It does not silently change the deployed Android
HTTP contract or add a second server. Existing backend authentication, upload
transport, transaction/version checks and authenticated asset serving remain the
caller's responsibility. Wire these functions into that existing backend worker;
the deployed app does not gain a video upload endpoint merely from this commit.

## Install and verify

```powershell
python -m pip install -e ".[media,test]"
python tools/run_checks.py
python tools/demo_media_pipeline.py
```

The demo uses a generated video and an explicitly substituted, reviewed synthetic
circuit fixture. It is a reproducible plumbing/diagnostic test, not extraction
accuracy on a real circuit. Outputs: `outputs/ml2-media/unreviewed.json`,
`diagnostic.json`, `frame-changed.json` and content-addressed `assets/` files.
No Gemini, weights or product-memory calls occur in this demo.

Optional local detection needs `requirements-detector.txt`, compatible trusted
Torch/Torchvision and weights configured through `LABVISION_ENDPOINT_WEIGHTS`.
No dependencies/checkpoints are downloaded by the processing path. Gemini remains
separate via `try_vision=True` and configured Gemini settings. YOLO proposals never
automatically become components, hole assignments, wire pairs or confirmations.

## Ingest ML1's existing result or run the bounded worker

```python
from reasoning.media import normalize_video, process_video, process_image

# If ML1 has already processed the file:
capture = normalize_video(ml1_video_result, board)

# Or inside the existing backend worker, from a staged local upload:
capture = process_video(
    staged_video_path, board,
    known_parts=experiment['reported_parts'],
    try_vision=False,
    deadline_s=60,
)

# The image path uses the same existing extractor and downstream handoff:
image_capture = process_image(image_bytes, board,
                              known_parts=experiment['reported_parts'])
```

`process_video` checks/stages a bounded immutable local copy and invokes ML1 in a
subprocess. Timeout kills the worker and temporary files are cleaned. Decoder /
detector work stays outside the caller's event loop and database transaction.
Input <=50MiB, source duration <=60 metadata seconds, at most6 returned frames,
returned JPEGs <=5MiB each and <=2000 pixels long edge. Original decoded limits
remain ML1's8.5MP. These limits do not prove a video depicts one unchanged circuit.
Do not fuse different circuit assemblies or inherit review across views.

Safe errors include `invalid_video_file_or_size`, `video_processing_timeout`,
`video_dependencies_unavailable`, `invalid_video_or_limits`,
`video_processing_failed`, `video_source_hash_mismatch`, `frame_receipt_mismatch`,
`candidate_image_mismatch`, and `invalid_selected_frame`. Provider/decoder stderr
and local filesystem paths are never exposed as media error messages.

## Persist, review and select frames

```python
from reasoning.media import restore_capture

asset_refs = capture.persist_assets(private_session_asset_directory)
state = capture.snapshot()  # JSON-safe; contains no JPEG bytes or temp paths.
# Persist state in the backend's authoritative session record.

capture = restore_capture(state, read_authorized_asset_by_hash)
# Apply actual student edits through the existing candidate controls, then:
capture.confirm(capture.candidate['revision'],
                acknowledgement='reviewed_all_connections_and_board')

next_capture = capture.select_frame('F2', try_vision=False)
updated_record = next_capture.apply_to_record(existing_record)
```

`persist_assets` stores immutable assets under content hashes. Return authenticated
asset URLs from the host backend; do not expose the private directory. The caller
owns authorization, atomic commit/version checks, upload validation, resource
quotas, original-video retention and deletion of all retained assets. Never take
an asset reader, private filesystem path or trusted snapshot from a mobile request.

Normalized video validates selected ID, unique frame IDs, actual image bytes,
receipts, dimensions and hashes, candidate binding and basic video/frame metadata.
It clears any inherited confirmation. Overlay metadata is bounded and unreviewed.
Coordinate systems refer to normalized returned JPEGs, not original video pixels.

Selecting another frame re-extracts from that frame's bytes, increments candidate
revision while retaining candidate identity, clears calibration and all review,
and invents no old-view hole assignments. Selecting the same frame is a no-op.
`apply_to_record` clears stale diagnosis/explanation, readings, checks, source
settings and old ID correspondences. It is a worker-side update helper, not an
HTTP handler; ownership/version/job checks and atomic persistence stay with the
existing backend. Core session tracking rejects changed image/frame bindings at
the same revision even if observed connectivity happens to be identical.

## Existing reasoning and ML3 output

```python
request = capture.request(
    approved_reference, explicit_component_map,
    safety_profile='instructor_approved_low_voltage',
    measurements=readings,
    student_expectations=expectations,
)
# Continue with the existing source-setting/voltage-source integration if needed.
# Then use diagnose_input(request) or advance_session(request, previous_state).

result = capture.diagnose(
    approved_reference, explicit_component_map,
    safety_profile='instructor_approved_low_voltage',
    measurements=readings, student_expectations=expectations,
)
# Send only result to the existing ML3 integration.
```

Reference wiring never enters ML1 extraction or video processing. The backend
still owns experiment lookup, instructor approval, component/port correspondence,
source settings and measurement conventions. Video input does not select a new
analysis engine or automatically support all five experiments.

The new `input.adapter='ml1'` delegates schema/part handling to ML1's actual
reasoning_input. Existing internal_v1 and ordinary ml1_v0.1 remain compatible;
legacy ml1_v0.1 now explicitly rejects extended/external observations instead of
losing semantics. Extended candidates require full review. Optional backend-only
`model_settings={'U1': {'gain': 100000}}` can bind the same explicit ideal OPAMP
model used by the approved reference. This is an assumption, not a photo reading;
inconsistent gain is rejected, and the diagnostic limitations state its origin.
Without it OPAMP gain remains unresolved. DIODE stays explicit unsupported behavior;
it is never silently replaced with an LED, short or wire. No DC/current/rectifier
or transient model has been fabricated.

The diagnostic response schema2.0, existing evidence labels and next-check flow
remain unchanged. Original1.0/image entry points keep working.

## ML2-owned ML3 compatibility handoff

Use `reasoning.ml3_bridge.explain` at the backend's existing explanation seam.
ML3 code/types/callback are injected; ML2 imports no ML3 or product-memory modules:

```python
from reasoning.ml3_bridge import explain
from mentor import DiagnosticResult, EvidenceItem

explanation = explain(
    result, session_id,
    diagnostic_type=DiagnosticResult,
    evidence_type=EvidenceItem,
    explain_callback=lambda value: service.explain_result(
        principal, value, query=description,
        equipment_id=equipment_id, channel=channel,
        simulated=simulated, now=now,
    ),
)
```

Preserve the existing backend's optional-probability `mentor.py` when combining
branches. Current `origin/Manit`c084375 requires probabilities and rejects the
backend's hypothesis_support keyword. The ML2 bridge detects that contract before
constructing its type. With optional-probability ML3 it invokes the existing
callback normally. With strict historical ML3 and no legitimate probabilities it
returns `status=fallback`, `wording_source=ml2_template`,
`model_status=ml3_requires_probabilities`, preserving the structured diagnosis and
permitted check; it does not invoke that explanation callback or fabricate scores.
This fallback is graceful degradation, not proof that the strict branch performs
normal ML3 explanation on ordinal input. ML3 context/outcome behavior is otherwise
unchanged and remains owned by the backend/service.

An actual trusted probability model may pass explicit `probabilities` plus
`probability_source` through the bridge. They must not come from mobile input or
be synthesized from ordinal support labels. Consumer/provider failures return a
safe labelled fallback without raw provider errors. Electrical safety refusal
still applies to fallback guidance. The diagnostic object itself is never mutated
or augmented with media fields.

Check actual branch snapshots locally without checkout or network/model calls:

```powershell
python tools/check_team_contracts.py
```

It compares original `origin/Manit` and the backend-integrated consumer using real
ML2 output, and saves `outputs/contracts/team-alignment.json`. Requires the named
Git refs to exist; refresh them separately when teammates push. This check does
not exercise HTTP uploads, credentials, hosted dependencies or real model accuracy.
