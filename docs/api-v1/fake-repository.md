# Offline session repository - demo only

`SessionRepository` is the application boundary for the finalized v1 contract.
`SessionModule` currently binds it to a singleton `FakeSessionRepository`.
No screen or Continue callback has been connected to it. The removed Render
upload client remains removed; this implementation performs no HTTP/Firebase calls.

## Files

- `data/model/session/SessionModels.kt`: serializable snapshots, messages, actions,
  events, response/error envelopes and binary image input.
- `data/repository/SessionRepository.kt`: suspend operation interface.
- `data/repository/FakeSessionRepository.kt`: in-memory fake backend behavior.
- `di/SessionModule.kt`: explicit Hilt demo binding.
- `app/src/test/.../FakeSessionRepositoryTest.kt`: deterministic virtual-time tests.

Kotlin serialization JSON 1.9.0 matches the existing serialization-core version.
Coroutine test 1.10.2 matches the existing coroutine dependency line. No networking
library or new permission was introduced.

## Demo labeling

The repository exposes `demoNotice`, each session has `mode=stub`, and every
assistant reply starts with `[DEMO]`. `assessment` is always null. It never produces
correct/incorrect verdicts, extracts real wiring, or contacts an instructor.
Catalog entries are available for *demo workflow* testing only, have a demo reason,
and advertise image_analysis=false and instructor_help=false.
Any future UI consumer must display `demoNotice` and the session mode persistently.

## Normal workflow

1. `getExperiments()` returns the five agreed experiments with version `1`.
2. `createSession(request, uuid)` starts awaiting_image and returns an upload action.
3. `uploadImage(id, version, image, description, uuid)` accepts JPEG/PNG up to 5 MiB,
   validates the image header and description, records an attachment receipt and
   returns a queued extraction job. `SessionImage` contains file bytes and MIME type;
   reading a content URI belongs in a future Android input adapter.
4. A background coroutine transitions queued -> running -> awaiting_input.
   `getSession()` is read-only: repeated GET-equivalent calls do not run jobs.
5. Synthetic sample wiring (the same demo resistor/ground sample for every
   experiment) exposes typed review and confirm actions. It is not image-derived.
6. A correction validates all changes before committing, increments candidate
   revision and requires new confirmation. Confirm queues a fake analysis job.
7. Fake analysis offers a sample voltage-entry action and visual-check action.
   These are software test inputs, not instructions to energize or measure a circuit.
8. After evidence actions complete, the session becomes ready, still without a
   diagnosis. Follow-up message events receive clearly labeled canned replies.
9. Close cancels pending fake work and makes the session read-only. A late worker
   cannot append results or reopen the session.

The fake supports only connection corrections specified by the current v1 schema.
Instructor-help events return ACTION_UNAVAILABLE; no human contact is simulated.

## Contract behavior

- Mutations are protected by a Mutex; versions and messages update atomically.
- Create/upload keys and event IDs replay the original response before stale-version
  checks. Reusing an ID with different input returns IDEMPOTENCY_CONFLICT.
- A replay can contain an older snapshot; clients must not overwrite newer state.
- STALE_SESSION / STALE_CANDIDATE include the latest snapshot in the typed exception
  and its error-envelope conversion. Stale confirmation does not modify wiring.
- Only one fake job runs per session. New operations while busy return JOB_IN_PROGRESS;
  close and replay remain available.
- Replacement images invalidate the candidate, pending actions and assessment.
  Subsequent candidate revisions never reuse older revision numbers.
- Invalid multi-operation corrections leave the original snapshot untouched.
- The response envelope serializes to request_id + data; httpStatus/replayed are
  local transport metadata. ConnectionChange uses the contract's operation
  discriminator; SessionEvent/SessionAction use type.

Use `Json { encodeDefaults = true }` for wire examples so required nullable/default
fields are included. Errors can be converted with `exception.toResponse()`.

## Scenarios and lifetime

The constructor defaults to Scenario.NORMAL. For tests/manual development it also
accepts EXTRACTION_FAILS_ONCE (returns a typed retry_job action, then succeeds on
retry) and REQUEST_CLEARER_IMAGE (returns upload_image instead of fabricated
extraction). unavailableExperimentIds allows testing unavailable catalog entries.

Default jobs have two 700ms delays. Tests inject a TestScope and advance virtual
time. The default application-lifetime coroutine scope is owned by the singleton.

This fake is single-client and has no authorization boundary. State, retry caches
and messages exist only in memory and are lost when the process ends. Same-instance
restoration is supported; persistence across app restarts is not. Retry caches are
kept for that instance's lifetime rather than implementing server retention.
Image URLs are intentionally non-resolving `https://demo.invalid/...` placeholders;
there is no signed URL service or durable image storage. Use the selected local URI
for a future demo image preview. Header validation is not full image decoding; the
real backend must enforce complete content validation and signed URL behavior.
