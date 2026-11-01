# Android video handoff

Owner: ML2/backend, following user-confirmed Android contract (2026-11-01).

1. Obtain a Firebase ID token. Send Authorization: Bearer on session operations.
2. POST /api/v1/sessions with JSON experiment_id, optional experiment_version and
   description, and UUID Idempotency-Key. Save session_id/session_version.
3. POST /api/v1/sessions/{session_id}/image, multipart field **image** containing
   MP4 with MIME **video/mp4**, plus expected_session_version as a text form field.
   Use a new UUID Idempotency-Key for upload. Let Retrofit create the boundary.
   Only MP4 is accepted, up to 50 MiB and 60 seconds. No JPEG/PNG input.
4. Poll GET session while extracting/diagnosing/completing. Refresh version before
   actions. Display messages and structured actions; preserve existing state labels.
5. GET /image for the selected review frame after extraction. This JPEG is an
   internal video frame, not an image upload option. Review connections with student.
6. Send existing nested events {event_id, expected_session_version, type, payload}.
   Explicit confirm_candidate is required before diagnosis. Measurements and
   source settings remain student evidence. ML3 explanation arrives in snapshots.
7. Use close_session for completion; DELETE is separate local-data deletion.

On 409 fetch latest state and reapply deliberately; never silently confirm a stale
candidate. Retry a lost response using identical key/body. On 401 refresh ID token;
503 indicates backend configuration/service availability. Extraction failure offers
explicit retry_extraction using the stored original video.

See BACKEND_API.md and schemas/backend-openapi.json for typed payloads.
examples/android/VideoSessionApi.kt is a Retrofit reference, not a compiled change
to the Android repository. APK/phone and live provider testing remain deployment checks.

Flow: MP4 -> ML1 sampled frames/selected extraction -> ML2 review + diagnosis ->
ML3 explanation. Media stays inside ML1/ML2/backend; ML3 diagnostic schema stays unchanged.

Grid/touch wire review: see [BACKEND_GRID_API.md](BACKEND_GRID_API.md) for new optional operations.

Grid/touch wire review: see [BACKEND_GRID_API.md](BACKEND_GRID_API.md) for new optional operations.
