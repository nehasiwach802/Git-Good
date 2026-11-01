# Android video integration — backend-circuitly

The active Android backend is **https://backend-circuitly.onrender.com**. Its public OpenAPI schema still identifies API **1.1.0**, but the upload contract has changed to MP4-only. The checked schema is saved as `deployed-openapi-v1.1.json` in this directory. This guide supersedes the earlier photo-only and preview-only Home instructions.

## What the app now does

1. Sign in using Firebase email/password or Google. Login also links to the dedicated Forgot Password screen.
2. Select an experiment. All six product choices, including Simple Wire, remain visible; exact published workflows determine availability. Known NAND/RC synthetic workflows are explicitly labeled demos. Missing or unapproved real workflows cannot start sessions.
3. On Home, select **Upload video** or **Record video**. The camera result and library videos have local playback/removal; no photo input is offered.
4. Enter a required description and press **Continue**.
5. The app copies and validates the video privately before creating a session, creates the session with a stable idempotency key, then streams the video upload with its own stable key.
6. Conversation polls the session while extraction/diagnosis jobs run. It shows server messages, processing/error states and explicit retry controls.
7. When the server returns the selected review frame, Android downloads it through the authenticated session endpoint. It is displayed with its frame ID/timestamp in the conversation and inline review form. Confirmation is disabled while a required frame has not loaded.
8. Structured actions submit corrections, explicit revision confirmations, component values, correspondence, source settings, measurements or observations. Chat prose is not parsed into authoritative actions.
9. **Exit conversation returns directly Home**, including during upload/processing. It cancels local work and forgets the active conversation; it does not send close/delete events or wait for the backend. Home retains its selected video/description. Already submitted server work may continue.
10. Home → **Settings → Sign out** clears Firebase/Google auth and account-specific local state.

## Actual deployed upload contract

Despite its legacy name, this endpoint now accepts an MP4 video:

```http
POST /api/v1/sessions/{session_id}/image
Authorization: Bearer <Firebase ID token>
Idempotency-Key: <UUID>
Content-Type: multipart/form-data; boundary=...
```

Multipart fields:

| Field | Value |
|---|---|
| `image` | The MP4 file, filename `circuit.mp4`, part MIME `video/mp4` |
| `expected_session_version` | The last known session version |

There is no `/video` route in this deployment. The field name `image` does not mean Android is uploading a photo. Do not rename the route or field in the client without a matching server change.

The deployed description explicitly says **MP4 video only; no JPEG/PNG input**. Upload returns a bare session snapshot (202), not a data envelope. The server retains `awaiting_image` and `upload_image` as legacy state/action names; Android labels them as video upload in the UI.

Limits enforced using the inspected backend validators:

- MP4 file, nonempty and with an ISO media `ftyp` header.
- At most **50 MiB**.
- At most **60 seconds**.
- At most **8.5 megapixels per input frame**; 1080p is recommended.

Android validates the size/container and decoded duration/dimensions before first session creation. The server remains authoritative for codec/decode/processing acceptance. The camera intent requests the size/duration limits, but a camera app may ignore them; post-recording validation still applies. Unsupported library videos are rejected before upload rather than silently renamed or converted.

## Other endpoints

| Operation | Request |
|---|---|
| Health / readiness | Public `GET /health`, `GET /ready` |
| Catalog | Authenticated `GET /api/v1/experiments` |
| Session creation | `POST /api/v1/sessions`, JSON `{experiment_id, experiment_version, description}`, idempotency UUID |
| Session snapshot/poll | `GET /api/v1/sessions/{id}` |
| Selected extracted frame | `GET /api/v1/sessions/{id}/image`, authenticated binary JPEG/PNG response |
| Structured event/message | `POST /api/v1/sessions/{id}/events` |

Each event has `event_id`, `expected_session_version`, `type`, and nested `payload`. Candidate revision belongs inside payload. Existing v1.1 event types and explicit confirmation acknowledgement remain unchanged.

```json
{
  "event_id": "00000000-0000-4000-8000-000000000001",
  "expected_session_version": 8,
  "type": "confirm_candidate",
  "payload": {
    "candidate_revision": 3,
    "acknowledgement": "reviewed_all_connections_and_board"
  }
}
```

## Transport, retries and local media

`BackendHttpClient` sends the current Firebase ID token, refreshes it once on a 401, and rejects responses if the account changes. JSON requests and binary frame downloads share the same auth boundary. Tokens and service-account keys are not logged or embedded in Android.

MP4 multipart bodies are written directly from the private file with a fixed Content-Length and bounded copy buffer. A 50 MiB video is not assembled into one in-memory ByteArray. The exact multipart body can be reopened/replayed after token refresh. Network failures do not automatically replay mutations.

The app retains create/upload IDs, the expected upload version and the exact pending event in SavedStateHandle for explicit retries and normal Android recreation. Retrying a failed upload does not create another session. A 409 refreshes the current session and discards stale events; a confirmation requires another explicit review. Uncertain creates can be reconciled with their original key even if the local video was subsequently lost. This is not a durable offline outbox or historical session browser after force-stop/data clearing.

Library videos are copied into app-private `noBackupFilesDir/session-videos` for validation/retry. Camera originals are app-owned cache files. Replacing/removing/resetting an app-owned recording deletes that cache file; user library files are never deleted. Private session video/frame copies are cleaned on the next start/account reset. Exit preserves only cleanup paths, not pending backend actions.

The selected frame is downloaded only after the backend supplies its image receipt. Its content/hash identity is tracked to avoid stale preview replacement. Only validated bounded JPEG/PNG bytes are stored for the local review preview. The client does not upload extracted frames or fuse wiring across video views; those operations belong to the backend.

## Main files

Paths are relative to the repository root.

| File under `app/src/main/java/com/example/gitgood/` | Responsibility |
|---|---|
| `data/backend/BackendModels.kt` | Bare v1.1 snapshots, video/frame metadata, messages and nested event models |
| `data/backend/BackendHttpClient.kt` | New base URL, JSON/binary requests, streaming body support, authorization/token refresh, account isolation and bounded responses |
| `data/backend/SessionApi.kt` | Video/session/event/frame interface |
| `data/backend/LiveSessionRepository.kt` | Exact legacy-named MP4 multipart endpoint and authenticated frame download |
| `data/backend/SessionVideoStore.kt` | Private streamed copy, MP4/size/duration/dimension validation, immutable retry file, frame cache |
| `di/BackendModule.kt` | Hilt binding for live transport, tokens, SessionApi and video store |
| `viewModel/ConversationViewModel.kt` | Validate → create → upload → poll → review flow, frame loading, stable retries, direct local Exit |
| `viewModel/HomeViewModel.kt` | Selected video/description and app-owned recording cleanup |
| `navigation/AppNavigation.kt` | Video-only picker, bounded camera capture intent, Continue wiring |
| `MainActivity.kt` | Selected experiment/video → conversation navigation and lifecycle |
| `ui/theme/screen/home/HomeScreen.kt` | Video actions, limits, description, Settings and enabled Continue |
| `ui/theme/screen/conversation/ConversationUiState.kt` | Processing and selected review-frame state |
| `ui/theme/screen/conversation/ConversationScreen.kt` | Processing feedback, chat, retry and immediate Exit |
| `ui/theme/screen/conversation/ConversationMessageBubble.kt` | Selected frame and timestamp caption |
| `ui/theme/screen/conversation/SessionActions.kt` | Inline assistant review/input card and server pending-action feedback |

The former `SessionImageStore.kt` was removed. The older `FakeSessionRepository`/`data/model/session` demo contract remains separate and is not the transport used by live screens.

## Verified and unverified behavior

Public checks on git-good-3 returned health `ok`, API version `1.1`, and readiness including `video_decoder: true`. They also reported:

- `firebase_credential_error: null`
- `firebase_permissions_verified: false`
- `approved_real_experiments: 0`
- `live_providers_verified: false`

These observations do not prove real circuit accuracy, full user-account permissions, or live model/provider quality. The inspected backend message handler still returns an existing explanation or a fixed review instruction rather than generating a new answer to each conversational question. The video pipeline may return manual/unresolved/calibration requirements; the client shows returned review requirements and does not fabricate missing calibration/analysis events that are absent from the deployed contract.

Validation command:

```sh
./gradlew :app:assembleDebug :app:testDebugUnitTest --console=plain
```

Contract/workflow tests use a local HTTP server and fake SessionApi/video storage. They cover MP4 MIME and legacy multipart field names, fixed body length, rejected images/oversized videos, duration/pixel validation, replay after auth refresh, stable upload keys, no duplicate creates, nested event revisions, conflicts, account isolation, selected frame metadata/download, foreground polling and immediate Exit without server events. Existing catalog/demo/theme tests are retained.

A physical-device signed-in MP4 → real deployed processing → reviewed diagnosis run has not been performed in this environment. Camera playback, real Firebase reset email delivery, backend processing outcomes and model accuracy must be checked on the target device. No backend data, environment variables, credentials or deployment were changed by this Android integration.

## Inline chat inputs

The Review required actions button and modal dialog were removed at the user’s request. Current server actions render as an assistant form inside the chat’s LazyColumn after the latest messages, using the same scroll area. Corrections, component values, label matching, source settings, measurements, observations and explicit revision confirmation are entered/submitted in this card. Optional circuit details expand inline; they do not gate the input fields. There is no separate popup or Done step.

Action identity and candidate revision keep unfinished fields stable across message-only session updates. New revisions/checks reset the corresponding forms. Inputs are disabled during submission; confirmation still requires a loaded review frame when provided and an explicit acknowledgement. Typed event payloads, version checks, normal chat messages and immediate Exit behavior are unchanged.

## Home settings and saved theme

The Home top-right action is now Settings. It opens a bottom sheet with exactly two options: a Dark mode switch (on = dark, off = light) and Sign out. ThemePreferences saves the explicit choice privately on the device; MainActivity applies it throughout the app through SettingsViewModel. Before the first explicit choice, the system theme is used. Sign-out retains this non-account preference. The effective app theme also controls system-bar icon appearance.
