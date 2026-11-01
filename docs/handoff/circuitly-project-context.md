# Circuitly / Git-Good — project context and handoff

Prepared November 1, 2026 (Asia/Kolkata), following the user's explicit request to upload the project's context through Meko MCP.

**Transfer status: NOT uploaded to Meko.** The configured Meko MCP endpoint rejected initialization with HTTP 401 Unauthorized. This document is the local fallback, ready for a later authorized upload after reconnection. It is a detailed handoff assembled from the available chat context and project files, not a verbatim export of every historical assistant/tool turn.

**Secret handling:** Service-account private keys, API keys, tokens, passwords, and credential JSON contents are intentionally excluded. Do not ingest the raw chat or credential attachments: a service-account private key was shared in this conversation. The user was instructed to revoke/replace it; completion of revocation was not verified.

## 1. Product and project identity

- Product name: Circuitly. Repository/project is also called Git-Good / gitgood.
- Android workspace: `/Users/apple/Desktop/gitgood`.
- Git branch observed: `neha`.
- Repository referenced during implementation: `nehasiwach802/Git-Good` on GitHub.
- Backend source inspected from branch `backend/android-connection-test`; deployment-source parity was not independently guaranteed. The public deployed OpenAPI schema was checked separately.
- Android application ID and namespace: `com.example.gitgood`.
- The user explicitly declined changing the application ID to `com.company.gitgood`; matching Firebase Android configuration was supplied instead.
- Firebase project ID: `circuitly-b1f4c` (a public configuration identifier, not a secret).
- Purpose: use a circuit's visual evidence and the student's description to review wiring, identify correctness or uncertainty through ML/reasoning, and continue the interaction in a chatbot-style conversation.
- The experiment is selected before preparing the circuit evidence. Structured review/confirmation/measurement actions accompany conversational messages.

## 2. Latest user decisions — authoritative over earlier work

1. **Home is now VIDEO ONLY.** Remove image upload, photo capture, image preview, and the Home-to-image-session submission path.
2. Home's two media input actions are **Upload video** and **Record video** using the device's camera app.
3. Show the selected or recorded video in a local playback preview; allow removing/replacing it and entering a description.
4. The user will provide an improved deployed model/backend soon. Do not invent or assume a working video API before its actual contract is supplied.
5. Current Home does not submit an image or video to the backend. Video transfer/analysis remains visibly unavailable pending the updated service.
6. **Exit conversation returns directly Home.** It must not wait for processing, send `close_session`, delete a session, or trigger another backend operation. Cancel local work and clear the active conversation state so another conversation can be started later. Preserve Home's input state during the navigation.
7. Home's top-right brand label was replaced by **Sign out**.
8. Add a dedicated **Forgot Password** screen accessible from Login.
9. Use a consistent light/dark palette, especially in chat. The earlier mix of fixed light colors and system-dark Material controls was unacceptable.
10. Show all five requested experiment choices, but accurately label backend availability. Missing analyses must not be fabricated.

Earlier photo-based behavior, instructions to close the server session on exit, and statements that the screen contains only the server's catalog are superseded by these decisions.

## 3. Requested experiments and actual support

The five product choices are:

| Stable Android selection ID | Display name |
|---|---|
| `not-gate-7400` | NOT Gate Using IC 7400 NAND Gates |
| `ohms-law` | Verification of Ohm’s Law |
| `rc-low-pass-filter` | RC Low-Pass Filter |
| `inverting-op-amp` | Inverting Op-Amp Amplifier |
| `half-wave-rectifier` | Half-Wave Rectifier |

`data/model/Experiment.kt` defines these choices, `ExperimentAvailability` (`AVAILABLE`, `DEMO`, `UNAVAILABLE`), and `resolveExperiments(server)`.

- Resolve published exact product IDs or names to exact server IDs, versions, and review contracts.
- Prefer an approved real workflow among matches.
- Explicit demo bindings exist only for `nand-not-example` (NOT gate) and `rc-lowpass-example` (RC filter), and only when the server marks them simulated.
- These retain their exact server identifiers and are visibly labeled synthetic demos, not approved real analyses.
- Missing or unapproved real workflows remain visible but cannot start analysis. Do not alias another demo to Ohm’s Law, the op-amp, or the rectifier.
- The last observed working catalog on the user's device contained the two synthetic examples. The other three workflows were not implemented/published by the backend during this work.
- Adding the five Android cards did NOT add five complete backend ML workflows.

The inspected backend registry declared R, C, V, OPAMP, and 7400 models, with connectivity, analog AC, and isolated NAND-as-NOT analyses. That declaration does not prove the capture pipeline or full experiment workflows support every model. Real Ohm's Law/rectifier behavior and op-amp capture need backend work and appropriate validation.

## 4. Android implementation overview

Stack: Kotlin, Jetpack Compose, Material 3, Hilt, Firebase Authentication, AndroidX Credentials/Google sign-in, Navigation3, Coil, Kotlin serialization, coroutines.

Observed Gradle settings:

- Android Gradle Plugin `9.3.3`; Kotlin/Compose compiler plugin catalog version `2.2.10`.
- Compose BOM `2026.02.01`; `buildFeatures.compose = true`.
- Built-in Kotlin support is used with AGP 9; do not blindly add `org.jetbrains.kotlin.android`.
- compile/target SDK 37; min SDK 24; Java source/target 11.
- Hilt `2.60.1`, KSP `2.3.9`, Firebase BOM `34.11.0`, Navigation3 `1.1.1`, lifecycle `2.11.0`.
- JSON serialization `1.9.0`; coroutines Play Services/test `1.10.2`.
- Existing builds compiled successfully. Android Studio's earlier screenshot showed a spelling inspection for “Circuitly,” not a Compose compilation error. The later runtime failure was Firebase authentication, not Gradle.

### Navigation

`MainActivity.kt` hosts an authenticated Navigation3 back stack:

- Auth: Splash, Landing, Login, Register, ForgotPassword.
- Authenticated: Experiments, Home, Conversation.

Firebase auth changes direct signed-in users to experiment selection and signed-out users from authenticated destinations to Landing. Sign-out resets account-specific Home, experiment, and conversation state. The conversation destination remains for the previous implementation and eventual video integration; the current video-only Home has no active analysis/Continue callback to it.

### Authentication and reset

- `AuthRepository.kt`: Firebase email/password registration/login, Google credential login, reset email, auth-state flow and sign-out.
- `GoogleSignInClient.kt`: Android credentials integration.
- `LoginScreenViewModel.kt` contains `LoginViewModel` (the file name and class name differ).
- `di/AuthModule.kt` provides auth dependencies.
- `ForgotPasswordScreen.kt` contains a dedicated themed screen and separate `ForgotPasswordUiState`.
- Login → Forgot Password pre-fills the entered email. Validate email, request Firebase reset email, show loading, a generic account-nondisclosing success message, or an error. Allow returning to Login.
- Reset state is separate from login state; a generation guard prevents canceled/previous requests from changing a new reset screen.
- Home Sign out uses the existing Firebase sign-out and Google credential clearing flow. Actual reset-email delivery was not tested with a user's account by the agent.

### Current video-only Home

Files:

- `ui/theme/screen/home/HomeUiState.kt`: `selectedVideoUri` and description; no selected image field.
- `viewModel/HomeViewModel.kt`: select/remove/reset a video; track app-owned recording path separately. Delete only app-owned recordings on replacement/removal/reset/VM clearing, never gallery videos.
- `ui/theme/screen/home/HomeScreen.kt`: Upload video, Record video, video preview/removal, description, Home Sign out, experiment Change, visible explanation that video analysis awaits the updated service.
- `navigation/AppNavigation.kt` → `HomeDestination`: video-only system picker and `ActivityResultContracts.CaptureVideo` camera launcher.
- A pending camera output path is retained with `rememberSaveable` during camera activity recreation.
- Camera records to an app-created `.mp4` file under `cacheDir/videos`, shared through FileProvider. Accept only a successful nonempty result. Delete unfinished files on cancellation/failure; retain the previous selected clip when recording is canceled. Show missing-camera/save/launch errors.
- `res/xml/camera_file_paths.xml` adds `camera_videos` for `videos/`. The legacy photo cache path remains for compatibility; it is not a photo input option.
- `data/CameraFileProvider.kt` remains the provider class; authority `${applicationId}.camera.files` is unchanged.
- `VideoPreview.kt` uses Android VideoView/MediaController without new playback dependencies. Preview does not autoplay audio, pauses on backgrounding, releases resources when removed/navigated away, and shows inline playback errors.
- No new broad storage, camera, or microphone permission was added: selection and recording use the system picker/external camera app.
- Home's image picker/capture/state/UI and `conversationViewModel.start(...image...)` call were removed.
- A disabled analysis placeholder is shown; no new backend endpoint or frame extraction is simulated.

### Theme

- `ui/theme/Theme.kt`: explicit light and dark Material schemes; dynamic wallpaper colors disabled by default.
- Dark: navy background (`#0C151D`), slate surface (`#16232E`), light body text (`#E5EDF3`), mint primary (`#69DDB8`).
- Light: cool slate background (`#EAF0F4`), light surface (`#F8FAFC`), dark text (`#172B38`), teal primary (`#006B53`).
- `Color.kt` exposes composable semantic getters backed by MaterialTheme: background, surface, primary/on-primary, body/secondary text, primary container, border.
- Auth, splash, Home, experiment cards, chat bubbles, input fields and dialogs use the same scheme; fixed white surfaces and purple defaults were removed from those screen styles.
- Light/dark Compose previews were added where relevant; actual device visual QA after the latest edits was not performed by the agent.

## 5. Backend URLs and contract history

Historical URLs supplied by the user included `git-good-1.onrender.com`, `git-good-2.onrender.com`, and `git-good-backend.onrender.com`. Early dummy integration was explicitly reverted before later real integration.

**Current configured base URL:** `https://git-good-2.onrender.com`.

- `BackendHttpClient.kt` holds this default base URL.
- The public OpenAPI was rechecked when switching back to this deployment and matched API `1.1.0`.
- Cached deployed schema: `docs/deployment/deployed-openapi-v1.1.json`.
- Older proposed contract: `docs/api-v1/contract.md`, `openapi.json`, and `examples.json`. This is not the same wire format as deployed v1.1.
- Legacy fake repository is kept separately; never assume its old envelope/field names match the production API.

### Deployed v1.1 image/session API (legacy client flow)

Public:

- `GET /health`
- `GET /ready`

Firebase ID-token authenticated:

- `GET /api/v1/experiments`
- `GET /api/v1/capabilities`
- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{session_id}/image` — singular `image`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/image`
- `POST /api/v1/sessions/{session_id}/events`

Session creation sends `{experiment_id, experiment_version, description}` and an `Idempotency-Key` UUID header. Description is required and capped at 2,000 characters. Responses are bare snapshots, not `{request_id,data}` envelopes.

Image upload uses multipart `image` and `expected_session_version`, with the same type of idempotency header. JPEG/PNG only, up to 5 MiB and 20 megapixels. The upload is allowed in `awaiting_image`; repeated image uploads are not a video batching interface. These legacy methods remain in source/tests but the new Home does not call them.

Snapshots include session ID/version, state, experiment ID/version, description, candidate revision/candidate, board, messages/actions, provenance and job/error metadata. Busy states include extracting, diagnosing and completing. Candidate data and actions are JSON objects to preserve evolving backend fields.

Event wire shape:

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

Candidate revision belongs inside payload. Supported event types include message, correct_endpoint, replace_candidate, confirm_candidate, set_correspondence, source_settings, measurements, check_result, retry_extraction and close_session. `close_session` is not now used by the app's Exit action. DELETE is a permanent deletion and must not be substituted for Exit.

- Correct endpoint identifies a component.pin, wire.a/wire.b, or port; choose hole or external terminal.
- Confirm only after explicit review of all connections/board for the displayed candidate revision.
- Measurements/source settings use structured fields, not parsing user chat prose.
- check_result uses check ID and observation text, not a guessed pass/fail enum.
- 409 means refresh and require another explicit review; do not automatically replay stale confirmation against a new revision.

### Live Android transport and workflow code

- `data/backend/BackendModels.kt`: catalog/create/message/snapshot/event/error models.
- `BackendHttpClient.kt`: bearer authorization, timeouts, bounded responses, one forced token refresh on 401, account identity checks, HTTP errors. Tokens are not logged.
- `SessionApi.kt`: injectable session interface.
- `LiveSessionRepository.kt`: JSON endpoints and multipart legacy image upload.
- `SessionImageStore.kt`: previous image preparation/private copy support, separate from workflow tests. Not used by current video-only Home.
- `di/BackendModule.kt`: Firebase ID token provider and live dependencies.
- `viewModel/ExperimentViewModel.kt`: authenticated catalog loading, five-choice resolution, errors, selection, sign-in recovery.
- `viewModel/ConversationViewModel.kt`: previous image-based session create/upload/retry sequence, snapshots, messages, typed events, foreground polling, saved pending operations and current immediate-local Exit behavior.
- SavedStateHandle retains operation identities for normal recreation. This is not a durable offline outbox or a historical server-session browser after force-stop/data clearing.
- Invalid/missing images must not create orphan first-time sessions. Uncertain creates retain their original key for reconciliation. Older snapshots cannot replace newer revisions.

## 6. Conversation UI and current model limitations

- `ConversationUiState.kt`, `ConversationScreen.kt`, `ConversationMessageBubble.kt`: typed UI state, server messages, local attachment preview, composer, errors/retry, notices/status and Exit.
- `SessionActions.kt`: controls driven by server actions, including review, connection correction, explicit candidate confirmation, retry extraction and check observations.
- `EvidenceForms.kt`: existing resistor/capacitor values, component/port correspondence, source settings, analog AC probe magnitudes and isolated 7400 logic observations using catalog metadata.
- Unknown actions show that additional support is required; controls are not inferred from assistant prose.
- Empty/manual candidate data may require extraction support or further manual circuit capture UI. Current correction controls cannot create a whole missing circuit.

The user's screenshots established that Firebase-authenticated catalog loading, legacy image upload/session messaging, and chat rendering could work. They did NOT establish model accuracy or a functioning free-form conversational model.

The inspected backend workflow's message branch appends the user's text and returns either the existing explanation or a fixed instruction to use review controls. It does not generate a fresh model answer to each question such as “Why?”. Review messages and “image received/extracting” are workflow messages, not proof of correct image understanding.

The last observed readiness report included:

- `status: ready`
- credential format error null
- `firebase_permissions_verified: false`
- `approved_real_experiments: 0`
- `live_providers_verified: false`

These are observations at the time of checks, not guarantees about future deployment state. The user had previously configured `VISION_ENABLED=false` and `QWEN_ENABLED=false`. Current live enablement cannot be inferred from the general readiness report alone.

Remaining model work: validate extraction on real circuit evidence; validate diagnosis against reviewed references/measurements; wire user messages/context to a conversational model if desired; implement missing experiment workflows and the video evidence pipeline. No fabricated correctness result should replace unsupported/unresolved evidence.

## 7. Firebase authentication incident and deployment guidance

An Android screenshot showed HTTP 401 `invalid_token`, message “Valid Firebase ID token required.” It was a runtime backend-authentication failure, not a Compose error.

Verified Android behavior: fetch the signed-in user's Firebase ID token with `getIdToken`, send `Authorization: Bearer ...`, refresh once on 401. Do not send a Google OAuth ID token or an Admin service-account key as the user's bearer credential.

The inspected `backend/auth.py` wrapped both credential initialization and `verify_id_token(..., check_revoked=True)` in a catch-all, returning the same 401 for every exception. Therefore the precise original underlying cause was not confirmed. Matching project IDs alone did not prove the key or permissions worked.

Recommended backend corrections:

1. Separate invalid/expired/revoked user-token errors (401) from credential/configuration/permission failures (503) and unexpected errors (500).
2. Log safe exception types privately; never keys or full bearer tokens.
3. Validate service-account JSON, matching project and key parsing instead of treating environment-variable presence as credential health.
4. Run a separate OAuth/Firebase Auth user-read diagnostic for revocation-check permission.

`docs/deployment/check_firebase_auth.py` was prepared as a secret-safe backend-environment diagnostic. It does not create or modify users. It was syntax-checked locally; execution with production credentials was not performed by the agent.

The user confirmed Render contained the entire service-account JSON, not just private_key. The JSON value must include outer braces and its original escaped newlines; do not paste the variable-name assignment into a Render Value field or wrap JSON in another string. Choosing Python/Java/Node/Go in the Firebase console changes only the sample code, not the service-account key type.

The user shared a private key in the chat. They were instructed to rotate/revoke it. Do not repeat or store that key. A requested one-line copy of a supplied service-account file was created at `/private/tmp/circuitly-service-account.min.json` with owner-only permissions and verified equivalent to its source. That credential file is NOT part of this handoff and must NOT be uploaded to Meko or committed.

Later device screenshots showed authenticated catalog loading succeeded after deployment changes; this confirmed that request was no longer blocked by the prior 401, not that all Firebase permissions/models were comprehensively verified.

## 8. Video architecture discussed — proposal, not implemented backend functionality

Recommended design:

1. Android selects/records and uploads the original video plus experiment/session information and description to the backend.
2. A backend worker validates media and extracts useful clear, nonduplicate frames.
3. Send timestamped frames to an image-based vision pipeline, or send video to a native video-capable model if the chosen model supports it.
4. Preserve frame IDs/timestamps and distinct circuit states. Do not merge wiring from different moments if connections changed.
5. Return job/session status and structured findings/actions for review.

Sampling around one frame per second was discussed as an initial test setting for a stationary circuit, not a validated universal rate. Blinking, switching and other temporal events may need denser sampling or native video analysis.

Suggested future route: `POST /api/v1/sessions/{session_id}/video`, multipart fields `video` and `expected_session_version`, Firebase bearer header and idempotency UUID, 202/job progress followed through the session endpoint. This was a proposal only. Do not implement Android against it without verifying the improved deployment's actual route, request/response schema, size/duration/codec limits and state rules.

The last checked deployed schema had NO video routes. Do not send videos to the current `/image` route, extract and repeatedly submit frames through it, or claim the existing upload UI transfers a video to the server.

The user explicitly stated they will provide an improved deployed model soon. Next integration should inspect its real OpenAPI/contract before making transport changes.

## 9. Earlier development history

The available user history also includes:

- Firebase Android setup using several replacement google-services JSON files; retain com.example.gitgood.
- Requests for SHA-1/SHA-256 signing fingerprints, Google sign-in dependencies, Hilt, Internet permission, AuthRepository/AuthViewModel/AppNavigation and LoginViewModel completion.
- A reference project Nudj at `/Users/apple/Desktop/Nudj` was used as requested for Firebase/navigation style. Do not assume its credentials or IDs belong to Circuitly.
- Initial Home layout, image picker/camera, description input, theme alignment, experiment-selection screen before Home, and later conversation UI. The image UI is now removed.
- Dummy endpoint integration was requested, explained/PDF documented, then explicitly reverted before the later real API work.
- An earlier proposed JSON contract was finalized for a fake/demo repository, followed by adaptation to actual deployed API v1.1 with different fields/routes.
- `SessionRepository.kt`, `FakeSessionRepository.kt`, `data/model/session/SessionModels.kt` and `di/SessionModule.kt` preserve the old demo contract. Live screens used SessionApi/LiveSessionRepository, not this fake binding.
- Fake repository scenarios covered idempotency, session/candidate conflicts, extraction/retry/review/evidence behavior and demo labeling. Fake responses must not be represented as real diagnoses.
- User requested explanations of changes and line-by-line API documentation/PDFs.
- Early Meko datapack listing requests appear in the available history; a successful enumeration was not established here.

## 10. Existing documentation and artifacts

Project documentation/artifacts observed:

- `docs/deployment/android-live-integration.md` — implementation guide, with latest video-only Home section authoritative over earlier photo sections.
- `docs/deployment/deployed-openapi-v1.1.json` — checked public deployed schema snapshot.
- `docs/deployment/check_firebase_auth.py` — safe server diagnostic.
- `docs/deployment/render-manual.env.example` — deployment example; do not add real credentials.
- `docs/api-v1/contract.md`, `openapi.json`, `examples.json`, `fake-repository.md` — older proposed/demo contract.
- `docs/ui/conversation-screen-walkthrough.md` — detailed conversation UI explanation.
- `output/pdf/circuitly-api-integration-line-by-line.pdf`.
- `output/pdf/git-good-firebase-navigation-guide.pdf`.

Historical guides may describe superseded photo/close-session behavior. Read this handoff's latest-decision section and current source first.

## 11. Validation and practical limits

Latest completed checks before this handoff:

```sh
./gradlew :app:assembleDebug :app:testDebugUnitTest --console=plain
```

Debug APK build succeeded. **49 unit tests, zero failures/errors** were observed in the generated reports. Groups include the existing demo tests, live transport contract tests, conversation workflow tests, catalog resolution tests, auth/catalog recovery tests, and light/dark contrast tests.

Tests exercise authorization headers, token refresh identity, no automatic write retries, nested event payloads, singular image multipart route, stale confirmations, signed-out/account isolation, no-orphan legacy image retries, monotonic snapshots, immediate Exit without close requests (including busy/in-flight/pending cases), five-choice availability and theme contrast.

Do not overstate this evidence:

- Unit tests use fakes/local HTTP fixtures; they are not live authenticated end-to-end model tests.
- Camera video recording/playback must be checked on the target device.
- Actual password-reset email delivery needs a device/account test.
- New video Home has no live transfer/analysis path until the updated backend is integrated.
- Real model correctness, live providers and all five complete real experiment workflows were not validated.

## 12. Recommended next work

1. Reconnect Meko MCP authentication and upload this sanitized handoff; verify persistence by read-back in the same datapack. Do not report upload success based only on an accepted response.
2. Obtain the improved model's deployed URL and actual video API contract.
3. Confirm backend auth, supported experiment IDs/versions and available analysis types.
4. Implement streamed/bounded video transfer, idempotency, session version handling and job polling using that contract. Avoid reading large videos wholly into memory.
5. Extend backend evidence processing for timestamped video frames/states or a confirmed native video model.
6. Restore the Home-to-conversation route for video only after the server path works; retain immediate-local Exit and existing structured review safeguards.
7. Complete/publish the missing experiment workflows with honest support/approval labels.
8. Verify physical-device recording, selection/cancellation, playback, reset-email flow, authenticated uploads, processing failures/retries and actual diagnosis quality.

## 13. Meko transfer blocker

Meko tool functions were not exposed in this chat's tool inventory. Local configuration nevertheless contained the MCP endpoint `https://mcp.mekodata.ai/mcp`. The configured enabled connection whose bearer environment variable was available was used for a direct MCP initialize request. It returned **HTTP 401 Unauthorized**.

No memory, conversation, knowledge-base or artifact write occurred. No remote persistence/read-back was possible. No credential values were printed or included in this document. Do not retry with a different credential, broader scope or datapack to work around an authorization error. Reconnect/refresh the intended Meko MCP authentication first.

Project agent attribution supplied for later authorized writes: `codex:gitgood`. Automatic Meko capture was reported down in this session. Do not blindly replay its capture backlog: raw turns contain the exposed service-account key and require redaction before ingestion.

## Later implementation update: git-good-3

After this handoff snapshot, Android was connected to https://git-good-3.onrender.com. This deployment accepts MP4 on the legacy-named POST /api/v1/sessions/{id}/image using multipart field image with MIME video/mp4. Current limits are 50 MiB, 60 seconds and 8.5 MP per input frame. Home Continue now creates a session and streams the selected/recorded video, with polling, retries and authenticated selected-frame review. Immediate local Exit is preserved. See docs/deployment/android-live-integration.md and current source for the authoritative implementation. The Meko upload remains unconfirmed/failed; this local update does not imply remote persistence.
