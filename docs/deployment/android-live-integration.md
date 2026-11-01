# Android integration with the deployed backend

The Android flow now uses **https://git-good-2.onrender.com**, API **1.1.0**. Its deployed schema, captured on November 1, 2026, is saved in `deployed-openapi-v1.1.json` alongside this document. This is the contract used by the live Android integration. The earlier proposed contract in `docs/api-v1` and its FakeSessionRepository remain separate demo work; their wire shapes are not sent to this backend.

## Try it on a device

1. Build/install the debug application and sign in with Firebase email/password or Google.
2. Choose one of the five product experiments. Android resolves availability from the live catalog. NAND and RC may use explicitly labeled synthetic demo workflows with their exact server IDs; missing or unapproved workflows remain visible and cannot start a session.
3. Choose or take a JPEG/PNG photo, at most 5 MiB and 20 megapixels. Enter a required description, up to 2,000 Unicode characters.
4. Continue. The app creates a session, uploads the image, opens the conversation, and polls while processing is active.
5. Read server messages and use **Review required actions** for structured input. Sending conversational text does not confirm connections or submit measurements.
6. Exit conversation returns directly home, including during processing or a failed request. It cancels local work and clears the active conversation state without sending close/delete events. Home retains its selected image and description. Already submitted backend operations may continue; exiting does not close the server session.

The backend readiness check currently reports `approved_real_experiments: 0` and `live_providers_verified: false`. Backend availability and Firebase configuration do not demonstrate that the vision/model pipeline can diagnose a real circuit. The app does not fabricate a correctness result when extraction or review cannot progress. In particular, an empty manual candidate needs extraction/provider support or additional manual circuit capture UI; connection corrections can only edit existing candidate endpoints.

## Requests and authentication

All requests below use the signed-in user's Firebase **ID token** in `Authorization: Bearer …`. No Firebase Admin private key or service-account JSON belongs in Android. A 401 triggers one token refresh, retaining the same request body and idempotency key. Account changes discard responses from the previous account. Network failures do not automatically replay writes.

| Operation | Android request |
|---|---|
| Catalog | `GET /api/v1/experiments` |
| Create | `POST /api/v1/sessions`, JSON `{experiment_id, experiment_version, description}`, `Idempotency-Key` header |
| Upload | `POST /api/v1/sessions/{id}/image`, multipart fields `image` and `expected_session_version`, `Idempotency-Key` header |
| Restore/poll | `GET /api/v1/sessions/{id}` |
| Event | `POST /api/v1/sessions/{id}/events` |

Session responses are bare snapshots. They use `session_version`, not the previous demo envelope or its field names. An event has this shape:

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

The app retains create/upload keys and an exact pending event in SavedStateHandle for retries and normal activity/process recreation. A 409 refreshes the snapshot and discards a stale event; confirmation always requires another explicit review. A force-stop, cleared app data, or a fresh launch without restored Android saved state is not a durable offline outbox or a server session browser.

## Files and responsibilities

Paths below are relative to the repository root.

| File under `app/src/main/java/com/example/gitgood/` | Responsibility |
|---|---|
| `data/backend/BackendModels.kt` | Deployed catalog, bare snapshot, create request, nested event and error models. Unknown response fields are tolerated. |
| `data/backend/BackendHttpClient.kt` | HTTPS requests, authorization, one token refresh, account checks, timeouts, bounded responses, HTTP errors. Tokens are never logged. |
| `data/backend/SessionApi.kt` | Session operations isolated from transport for workflow regression testing. |
| `data/backend/SessionImageStore.kt` | Validates and stores private image copies separately from session requests. |
| `data/backend/LiveSessionRepository.kt` | Live endpoints, serialization, multipart upload and size/type checks. |
| `di/BackendModule.kt` | Hilt client with Firebase ID token provider. |
| `viewModel/ExperimentViewModel.kt` | Authenticated catalog loading, retries, exact experiment ID/version selection, loading/error state. |
| `data/model/Experiment.kt` | Defines the five product choices, stable selection IDs, availability and explicit synthetic demo bindings; retains exact backend IDs and review contracts. |
| `viewModel/ConversationViewModel.kt` | Image validation/private copy, create/upload sequence, snapshot state, message/event retries, foreground polling and immediate local exit. |
| `MainActivity.kt` | Authenticated navigation, Continue wiring, conversation lifecycle and exit-to-home navigation. |
| `navigation/ScreenRoute.kt` | Serializable conversation destination. |
| `navigation/AppNavigation.kt` | Connects Home's Continue callback while retaining the camera/picker flow. |
| `ui/theme/screen/experiment/ExperimentScreen.kt` | Live catalog loading/error/retry and provenance labels. |
| `ui/theme/screen/home/HomeScreen.kt` | Required description and visible upload limits. |
| `ui/theme/screen/conversation/ConversationUiState.kt` | Server status, provenance notice, input availability and exit state. |
| `ui/theme/screen/conversation/ConversationScreen.kt` | Chat callbacks, live state and structured action entry point. |
| `ui/theme/screen/conversation/SessionActions.kt` | Actions driven by `snapshot.actions`: retry extraction, review, endpoint correction, explicit revision confirmation and check observations. |
| `ui/theme/screen/conversation/EvidenceForms.kt` | Existing resistor/capacitor values, component/port correspondence, source settings, analog AC probe readings and 7400 logic observations using catalog metadata. |
| `di/SessionModule.kt` | Documents that the old binding is demo-only; live screens inject LiveSessionRepository. |

Unknown actions are shown as requiring additional app support. Analog AC and 7400 measurement forms follow the backend's current validation rules; future experiment analysis engines may need additional forms. The app does not infer controls from assistant prose, invent mappings, automatically confirm a candidate, or claim instructor authorization on the user's behalf.

Images are copied to app-private `noBackupFilesDir` before upload, so picker access is not needed for an interrupted retry. They are not embedded in saved state or placed in public storage. The current private copy is removed on account reset or when starting the next conversation. The preview uses this local copy; downloading images for arbitrary historical sessions is not implemented.

## Validation

Run:

```sh
./gradlew :app:assembleDebug :app:testDebugUnitTest --console=plain
```

`LiveSessionRepositoryTest` uses a local HTTP server to exercise bearer authorization, catalog parsing, bare snapshots, required description, multipart path/fields, nested confirmation revision, token refresh with unchanged mutation identity, conflict handling, close-vs-delete semantics, no automatic retry after server failure, signed-out rejection, account isolation and unsupported image rejection. Existing demo repository tests remain separate.

Public readiness and the deployed schema were checked directly. A signed-in device's full Firebase → image → model → diagnosis flow has not been executed in this environment; it must be verified with the user's existing account and the configured backend providers. No backend environment variables, credentials, deployment, or server data were changed for this task.

## Retry and restoration fixes

Invalid or missing images are rejected before a first create request. An uncertain create retains its original key and can be reconciled and explicitly closed even if the cached image is subsequently lost. Confirmed closure clears unfinished setup state, allowing a new conversation. Account resets clear the previous review metadata. Home remains on its restored destination while the catalog loads, updates the experiment name when loading finishes, shows catalog errors, and disables Continue until a valid selection is available.

`ConversationViewModelTest` exercises missing images, uncertain-create reconciliation, close cleanup, stable message retries, stale confirmations, busy exits, account reset, and monotonic snapshot revisions.

## Theme and five-experiment menu

All screens now use a shared teal/slate Material scheme. Dark mode uses navy backgrounds, slate message/input surfaces, light text and mint accents. Light mode uses cool slate backgrounds. Device wallpaper colors are disabled by default so they cannot change control colors independently of screen backgrounds. Auth, home, experiment cards, chat bubbles, dialogs and input fields use the same scheme. ThemeContrastTest checks text, accent and button color pairs in both modes at a minimum 4.5:1 contrast ratio.

The menu always contains the five requested experiments. resolveExperiments matches published exact product IDs/names, prefers an approved real workflow, and explicitly supports the existing nand-not-example and rc-lowpass-example records as labeled demos. It never substitutes those demos for Ohm’s Law, the op-amp, or the rectifier. Pending choices can be inspected but Continue is disabled. ConversationViewModel also rejects attempts to start an unavailable workflow. No backend catalog, model capability, approval or deployment was changed by this UI update.

Exit behavior was revised at the user’s request: navigation is immediate, independent of server status. Earlier references to waiting for a close event describe the previous implementation. Regression coverage includes exit during a running request, exit during processing, and leaving an unsent pending event without submitting it.

## Video selection (Android)

Home now offers Upload video beside Upload image and Take photo. It uses the Android system picker restricted to videos, with local VideoView playback controls, removal, inline playback errors, pause when backgrounded, and resource cleanup on removal/navigation. Only one photo or video is selected at a time; switching media keeps the description. No broad storage permissions or new playback dependencies were added.

The current deployed API has no video-upload endpoint. Video selection therefore does not create a session, upload bytes, extract frames, or invoke ML. Home explains that video analysis is unavailable and disables Continue for video attachments. Photo analysis continues through its existing endpoint. Video recording and server video processing are separate future work.
