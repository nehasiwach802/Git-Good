# Git-Good project context

Last updated: 2026-11-01 (Asia/Calcutta).
Maintainer: Codex acting as ML person 2.
Build memory: `gitgood-build`. Agent namespace: `codex:Git-Good`.

## Purpose and ownership

AI Lab Mentor diagnoses electronics experiment problems using confirmed circuit
connectivity, simulated readings, student observations and evidence-linked checks.
Deterministic components produce findings; the explanation layer communicates them.

- ML1: photo-to-candidate circuit, component identity, uncertainty and image evidence.
- ML2 (this repository's current implementation): validation, netlist comparison,
  SPICE adapter, measurement comparison, diagnostic ledger and next-check selection.
- ML3: explanation, authorized product memory, equipment aggregation and knowledge lifecycle.
- Android: capture, confirmation, measurement entry and diagnostic presentation.
- Shared backend/instructor workflow: orchestration, authorization and review.

## Implemented baseline

### Integrated Android backend (2026-11-01)

Current branch: backend/android-connection-test. Actual ML1 source imported from
origin/Abhiram 07b38aa and ML3 from newly pushed origin/Manit c084375; previous
missing-ML3 blocker is superseded. Kept ML2 size/revision/overflow hardening and
ML1 external-terminal 0.2, rail review and annotation features together.

backend/app.py now provides authenticated API 1.1: experiment/capability lookup,
multipart session creation (202), snapshots, typed revision-checked/idempotent
events, image retrieval and deletion. SQLite persists images/sessions/jobs/events;
one background worker connects real labvision.upload.extract_upload,
reasoning.api.diagnose_input and ML3Service. Student review precedes reasoning;
correction invalidates review. Provider failure yields manual unknowns, not fake
connections. Structured chat supports review, source settings, readings, checks
and completion; free text does not autonomously edit circuits.

Firebase Admin verifies Android ID tokens; missing configuration fails closed.
Owner and lab checks protect records. ML3 HTTP service is mounted at /api/v1/ml3
with authoritative server callbacks, personal-memory isolation, outcome ledger,
instructor equipment review and optional supplementary Qwen wording. No product
datapack calls were made by the coding agent. Missing memory yields an explicit
unavailable state; uncertain outcome writes are retained for reconciliation.

User preference: probabilities are preferred in ML3. Supplied ML2 probabilities
are preserved and displayed. Current ML2 only supplies ordinal support: honest
integration returns cause_probabilities=null and probability_status=not_calibrated.
No arbitrary ordinal-to-percentage mapping was introduced. Probability calibration
still requires an agreed method and labelled validation data.

Contract: docs/BACKEND_API.md, schemas/backend-openapi.json and separate mounted
schemas/backend-ml3-openapi.json. Deployment: docs/BACKEND_DEPLOYMENT.md and
Dockerfile.backend now copy all modules and install ngspice. Requires one instance,
one uvicorn worker and a persistent DATA_DIR volume. Bundled two reference records
are synthetic examples, workflow_approved=false; real approved experiment catalog
and source/equipment bindings remain operator/instructor configuration.

Legacy /api/sessions remains an explicit deprecated smoke endpoint, separate from
actual /api/v1/sessions. Existing public Render URL git-good-1.onrender.com was
previously verified for that smoke version only; these local changes are not
committed/pushed/deployed by this task. Docker itself is unavailable locally.

- Python 3.11+ package with no third-party runtime Python dependencies.
- Validated SI-valued R/C/V/ideal-OPAMP circuits, wire alias normalization and
  topology comparison independent of net labels; passive terminal reversal allowed.
- Missing/extra components, wrong types/values/source settings, connectivity
  mismatch and conservative terminal-level missing/unexpected connection evidence.
- Restricted ngspice single-frequency AC magnitude adapter, timeout and explicit
  unavailable/failed results; generated internal net names and strict output checks.
- Measurement tolerances, independent supported/unresolved hypotheses, stable
  evidence IDs and prioritized next checks with UI input metadata.
- Optional backend session helper that stores snapshots in caller-provided state;
  current diagnosis is recomputed so corrected faults do not retain old support.
- Local HTTP API, fixture CLI, request/response JSON Schemas, example responses,
  synthetic diagnostic cases and CI configuration.
- Integrated ML1 labvision package, fixtures and upstream tests from Abhiram
  db8a1ce. This supersedes the earlier absent-source blocker in build memory.
- Shared dispatcher reasoning.api.diagnose_input accepts existing analog JSON,
  analysis=7400_as_not for reviewed ML1 candidates and isolated Boolean checks,
  and analysis=analog_from_vision for reviewed R/C with explicit source/port maps.
- Session history now also supports ML1 candidate/board identities, stale revision
  rejection and detection of physical edits without incrementing revision.
- tools/demo.py runs four synthetic input JSON files and saves actual responses
  under outputs/demo/. tools/run_checks.py fails for failures OR skipped tests.
- Real ngspice 47 runs from the ignored local .tools/Spice64/bin/ngspice_con.exe;
  environment override NGSPICE_EXECUTABLE and PATH are also supported. This binary
  is not committed or distributed with the package.
- Added generalized request/response 2.0 while preserving 1.0 routes. New
  observations.py validates partial internal observations and versioned reference
  records; adapters.py isolates current ML1 0.1 and internal observation input.
- generalized.py compares reference vs observed evidence without repairing model
  proposals. Unknowns, alternatives and unconfirmed differences do not establish
  wiring faults. Independently confirmed values/directional relationships may
  still supply evidence while other observations remain unresolved.
- registry.py declares model pin semantics, required values, supported analyses
  and a registry version. Unknown models/analyses yield capability gaps rather
  than guesses. RC and a resistor divider reuse the same analog runner.
- Explicit component_map and optional port_map resolve identity without matching
  arbitrary labels. Simulation requires resolved review/values/ports. Draft
  references cannot establish confirmed wiring faults.
- ExperimentCatalog supports backend ID/version lookup and defensive copies;
  reference configuration, optional approved checks and reported problem text
  remain separate from extraction. No final five experiments are selected.
- Version-2 sessions bind reference/model-registry versions and observation/board
  identity; physical edits require a revision increase. tools/demo_generalized.py
  writes examples to outputs/generalized/; schemas and docs/GENERALIZED_CORE.md
  document the internal development contract, not a finalized future ML1 format.

## Contracts and decisions

Implementation decision owner: Codex acting as ML person 2. These describe the
current development interface; final experiments and proposed extensions remain
subject to team agreement.

- [Authoritative integration contract](docs/contract.md): request version 1.0,
  stable instructor component IDs, per-component student confirmation, SI numeric
  values, AC magnitude in volts, explicit student probe mapping for renamed nets.
- [Request schema](schemas/diagnose-request.schema.json) and
  [response schema](schemas/diagnose-response.schema.json): structural contracts;
  runtime validation also checks references, uniqueness and finite numbers.
- Evidence/check IDs are opaque and scoped by the backend session. New response
  metadata is additive; IDs do not indicate check completion or authorization.
- Apparatus suspicion requires source-linked substitution evidence; mismatched
  readings alone and simulation failures do not establish equipment faults.
- Backend authorizes the approved low-voltage workflow; the request flag itself
  is not a safety assessment. The HTTP server is local development infrastructure.
- [Development and handoff notes](docs/development.md) explain tools, session
  integration, remaining decisions and testing limitations.
- [ML1 integration review and demo](docs/ML1_INTEGRATION_REVIEW.md) supersedes
  earlier review notes: actual source inspected, explicit candidate envelope,
  no automatic confirmation, no reference-answer leakage into extraction.
- ML1 owns candidate/export 0.1. ML2 owns the optional analysis envelope 1.0;
  schemas/vision-diagnose-request.schema.json describes it. Digital observations
  are explicit integer binary rows, not inferred TTL levels from voltages.

## Latest verification

Latest verification: integrated backend implementation, 2026-11-01.

- `.venv-backend/Scripts/python.exe tools/run_checks.py`: 260 tests passed,
  zero failures/skips. Includes imported ML1/ML3 suites, real ngspice RC/op-amp,
  actual backend ML1 -> ML2 -> ML3 flow, analog source settings, background worker,
  Firebase verification mocks, ownership/lab boundaries, streaming limits,
  idempotency/stale revisions, recovery, mounted ML3 and probability preservation.
- `python tools/demo_backend.py`: passed; synthetic HTTP transcript saved to
  outputs/backend/synthetic-transcript.json. Sequence: extracting -> review ->
  diagnosis/measurements -> evaluated -> completed. No product memory configured;
  final memory outcome truthfully requires reconciliation, not claimed stored.
- Package wheel build passed; `pip check` reports no broken requirements.
- `git diff --check`: passed (line-ending warnings only).
- Real-photo accuracy, live Firebase/Gemini/Qwen/Meko, Docker image build, phone
  integration, remote CI and deployment of these changes were not verified.
- Existing ngspice47 local binary is ignored; Dockerfile installs ngspice separately.

## Blockers and next steps

1. Keep ngspice configured on each deployment machine and run the no-skips checks;
   the local installation and real RC/op-amp tests are now working.
2. Agree on final experiments, physical device models, source conditions and
   required analyses. Existing RC/op-amp JSON files are simulated fixtures only.
3. Validate ML1 extraction on labelled real photos and actual board profiles.
   The supplied dummy candidates are synthetic; real-photo extraction had not
   produced a complete netlist in ML1's first-run report.
4. Finalize instructor-approved probes/checks, measurement conventions/tolerances,
   equipment metadata and ML3 evidence semantics.
5. Configure deployment disk, Firebase/provider credentials, approved experiments and
   personal-memory mappings; test Android against deployed API 1.0. Define retention.

Current limits: ideal op-amp excludes rails/clipping; no DC/transient/phase modes,
calibrated probabilities or calculated information gain. Ambiguous wiring cannot
always be localized. Digital mode is isolated 7400 NAND-as-NOT only, without TTL
voltage/timing/loading or device-health simulation. Vision extraction code is
present but no paid/live extraction ran for integration. Live provider acceptance and Android phone-side integration remain unverified;
backend orchestration, authentication and persistent storage are now implemented. Software tests cannot prove every possible physical fault.

## Context maintenance and Meko

File-change overview lookup title: `Git-Good file changes summary - 2026-10-31`.
Save the overview as ordinary memory under `codex:Git-Good` in `gitgood-build`;
do not promote that overview out of memory. Promote teammate-facing decisions
separately. The overview includes modified tracked files and untracked additions,
which `git diff --stat` alone does not show. It summarizes working-tree work, not
a committed release. Inspect promoted/shared memory as well as ordinary memory;
earlier summaries may have been promoted after their initial save.

Follow [AGENTS.md](AGENTS.md) before and after every task. Refresh this file when
state changes, save a matching concise summary to `gitgood-build`, and promote
changed teammate-facing decisions with their owner. Recall may return older
information; reconcile with the checked-out repository and latest actual checks.

Synchronization is performed by the coding agent during tasks, not by a running
background service. If Meko fails, record pending synchronization here and retry
on the next task. Never access product datapacks or store secrets, personal data
or raw student sessions in this context or the build datapack.

## Deployment repository preparation (2026-11-01)

Owner: ML2/backend Codex, following the user's request to prepare the repo.
Added Render Blueprint render.yaml targeting git-good-1/backend branch, explicit
Dockerfile, one paid starter instance, 1 GB persistent disk, shutdown grace and
manual deploy trigger. It does not provision/purchase resources automatically.
Added .env.example, pinned verified direct runtime requirements, Docker entrypoint
that initializes volume ownership then drops to appuser, container health check,
LF shell attributes and container build/volume/HTTP smoke workflow in CI.
Added backend.preflight CLI and expanded /ready checks for credential presence,
solver, storage, catalog, worker and enabled providers. --production additionally
requires approved real experiments. Checks never call model/product services or
print secrets. Four deployment tests added. CI Python tests use runtime pins.

Verification: 260 tests passed, zero skips/failures; pip check passed; Render YAML
parsed locally. Preflight correctly reports current missing Firebase/provider
configuration and zero approved real experiments. Docker is unavailable here;
container build/boot is configured in CI but not claimed executed. Host credentials,
approved experiment configuration and commit/push/deploy remain external steps.
See docs/BACKEND_DEPLOYMENT.md for the concrete procedure.

## Deployment fix: ml3_http import (2026-11-01)

ML2/backend Codex fixed an omitted runtime module: Dockerfile.backend COPY and
setuptools py-modules now include ml3_http.py. Docker build also imports the full
FastAPI app before image completion. Added an isolated-artifact regression test
that copies only Docker-declared runtime files and boots the app without checkout
imports. Package wheel rebuilt and confirmed to include ml3_http.py. No credentials
or product datapacks accessed. Commit/push and rebuild Render deployment required;
no remote deployment performed by this fix. Docker unavailable locally.
Verification for this fix: 261 tests passed, zero failures/skips; wheel build and module inspection passed; git diff --check passed.

## Readiness/contract troubleshooting (2026-11-01)

User reports deployed /ready503 and Android contract mismatch. Local readiness
shows credential presence and enabled vision configuration are blockers. The
approved_real_experiments count is informational for /ready; only CLI --production
requires it to be positive. Do not mislabel synthetic records as real approvals.
Recommended host config uses Firebase secret file plus GOOGLE_APPLICATION_CREDENTIALS,
matching project ID, and VISION_ENABLED=false/QWEN_ENABLED=false for manual/template
integration. Real experiments still need instructor-approved records. Requested
Android finalized contract branch/path or exact mismatch; message did not contain
it and current cached origin/neha tree exposes no matching contract. Live ready/
OpenAPI retrieval via web tool failed, so remote state not independently verified.
No runtime changes, tests or deployment performed for this troubleshooting task.

## Android finalized contract alignment (2026-11-01)

User supplied the four concrete mismatches and explicitly confirmed the proposed
exact upload route/envelope. Owner ML2/backend implementing the Android contract:
POST /api/v1/sessions is now JSON metadata creation (201 awaiting_image), then
POST /api/v1/sessions/{session_id}/image accepts multipart image and
expected_session_version (202 extracting), each with UUID Idempotency-Key.
Events use {event_id,expected_session_version,type,payload} with typed nested
payloads and close_session. Snapshots use session_version and api_version1.1;
OpenAPI info.version is1.1.0. Flat events/expected_version are rejected on the
canonical route. The prior combined multipart and flat interface remains only
under /api/legacy/v1/sessions; old smoke /api/sessions remains diagnosis-free.

Added backend/contract.py adapter and persisted upload receipts table. Creation
without image queues no model work. Upload image+job+version persist atomically;
retries replay the original response, conflicts and stale versions return409.
close_session on an idle draft closes with no diagnostic outcome; evaluated
sessions complete ML3 outcome processing before exposing closed. Busy sessions
reject edits/close. A closed session is immutable; deletion remains separate.

Updated actual OpenAPI, Android contract, deployment guide, archived v1 contract,
README and synthetic demo. Docker build import and isolated-artifact regression
now assert the new separate upload route instead of a fixed old API version.
Existing session records are preserved; SQLite creates the new receipts table.
Firebase/provider readiness configuration and instructor approvals are unchanged.
No credentials were read or host settings changed; commit/push/redeploy required.
Verification: 268 tests passed, zero failures/skips; API1.1 synthetic demo passed; package wheel build passed. Docker/live deployment not run locally.

## Firebase error/readiness fix (2026-11-01)

Owner ML2/backend Codex, following user's request to solve the assessed issues.
backend/auth.py now separates invalid/expired/revoked tokens, disabled/deleted
users and tenant mismatch (401), credential/OAuth/IAM/service failures (503), and
unexpected initialization/verification/claims failures (500). Verification and
check_revoked=True stay enabled. Private logs contain only controlled stage and
exception type, not provider messages, tokens or keys. Cached app project checked.

backend/firebase_credentials.py validates either nonblank inline JSON (precedence)
or GOOGLE_APPLICATION_CREDENTIALS secret file: service-account object, matching
project_id, required string fields and Firebase Admin private-key loading. No
ambient/user ADC fallback on this explicit service-account deployment path.
Preflight shares that offline validator, reports safe credential reason codes,
and explicitly firebase_permissions_verified=false. It makes no Google calls.

Added operator-only python -m backend.firebase_diagnostic --live: OAuth refresh
and separate Auth user-read permission check, bounded network timeouts, random
synthetic nonexistent UID by default. Reports stages/exception classes only;
no records/access tokens printed. Never invoked by readiness or this coding task.
Updated deployment/API docs and env template. Expanded mocked auth tests and
synthetic ephemeral-key credential/diagnostic tests; no real key fixtures saved.

Verification: 283 tests passed, zero failures/skips; package wheel built; diff
check passed. Real credential file not read, real OAuth/IAM not tested, no keys
revoked or Render secrets/deployment changed. Operator must replace exposed keys
if applicable, supply matching project credentials, redeploy, and run live
permission diagnostic on host. Vision remains a separate Gemini configuration.

## MP4-only backend integration (2026-11-01)

Working branch backend/android-connection-test; uncommitted integration imports
ML1 Abhiram393732a and ML2 tanu1059ff8 callable media/review/bridge modules.
ML3 root implementation retained unchanged. User/Android contract owner explicitly
confirmed existing POST /api/v1/sessions/{id}/image and multipart image field
now contain MP4 only. JPEG/PNG uploads return415; old combined image POSTs410.
JSON creation, expected_session_version, nested events and close_session unchanged.
Historical awaiting_image/upload_image labels remain for Android compatibility.

Video staging streams to private persistent storage, validates MIME/signature/size,
enforces 50MiB file /51MiB envelope, queues durable extraction with idempotent
receipts. ML1 runs in bounded killable process; source retained for explicit retry.
Up to6 internal JPEG frames stored privately; selected frame exposed through GET
/image for review only. Media metadata stays in ML1/ML2/backend, never ML3 schema.
Student confirmation and measured source settings remain required; no invented
probabilities. Strict original ML3 can use explicit safe explanation fallback
when valid probability scores are unavailable.

Docs: BACKEND_API.md, BACKEND_DEPLOYMENT.md, ANDROID_VIDEO_HANDOFF.md; generated
OpenAPI updated and Retrofit reference provided (not built into Android app).
Runtime adds OpenCV/NumPy; optional endpoint detector build/weights separate.
Verification:322 tests passed, no failures/skips; synthetic MP4 backend demo
completed create/extract/review/diagnose/measure/close with actual local interfaces.
pip check and git diff --check passed. Providers/auth mocked in tests; no live
credentials read, Docker build, APK test, push or deployment performed.
Next: review/commit/push branch, redeploy configured service, verify real Firebase
auth/providers/approved experiments and Android MP4 flow. No automatic quality
guarantee for model extraction; manual review remains essential.
Matching build summary saved to gitgood-build; synchronization succeeded.

## Pre-push verification (2026-11-01)

ML2/backend rechecked current backend branch:322 tests pass with no skips;
synthetic MP4 transcript reaches closed after extraction/review/diagnosis/readings.
Actual local uvicorn HTTP boot: /health200, /openapi.json200 (API1.1.0), /ready503.
Local readiness lacks Firebase project/credentials and enabled vision settings;
zero approved real experiments. Decoder/ngspice/worker/storage/catalog checks pass.
No real auth/provider/phone or remote deployed service verification performed.
Android route/field/event contract preserved, with agreed MP4-only MIME input;
obsolete combined image POSTs return410. No commit/push/deployment performed.

## README architecture and laptop setup (2026-11-01)

Owner ML2/backend Codex, user requested README first; merge-conflict resolution
and main consolidation explicitly deferred to the next task. Recalled ordinary
and promoted/shared gitgood-build architecture decisions, reconciled with current
backend branch commit333199d (video integration now committed by user).
Replaced stale reasoning-only README with problem statement, proposed solution,
ML1/review/ML2/ML3/Meko flow diagram, actual tech stack, current capability limits,
and laptop installation, offline demo, authenticated server and Android API steps.
Clarified MP4-only legacy image field, server-only credentials, manual-review
requirements, synthetic catalog approvals, optional detector/Gemini/Qwen/memory,
and separate Android app. No fallback proposal presented as an accepted redesign.
Verification this task: backend MP4 demo, generalized demo, RC validate/diagnose
commands passed in existing .venv-backend; README local links/fences/sections and
upload fields vs actual OpenAPI passed; diff check passed. Prior322-test release
result retained as historical verification, full suite not repeated for docs-only
change. Fresh laptop install, real auth/providers, APK and deployment not tested.
Only README/context changed; branches not switched/merged, no push/deployment.
Matching summary saved successfully to gitgood-build.

## Final ML1 automatic-grid handoff -> ML2 (2026-11-01)

ML1 shared memory identified newly pushed Abhiram ea67b52 and authoritative
docs/AUTO_GRID_HANDOFF.md. Fetched actual commit and selectively imported its
autocalibration runtime/video opt-in, focused tests, handoff/preview/practice files;
retained existing backend/ML2 hardening and uncommitted README work. Current branch
remains backend/android-connection-test; no main merge/cherry-pick/index changes.

ML2/backend owner Codex: reasoning/grid.py validates bounded geometry/image and
board binding, finite complete central-grid coordinates, invertible projective
transform and quality metadata; reconstructs inverse and strips false human checks
and review flags. Invalid grids fall back to manual entry, not session failure.
Media worker forwards opt-in auto_grid, preserves normalized per-frame metadata
and selected ml1.grid_proposal; AUTO_GRID_ENABLED=false by default. Correct actual
10-70-row central-board profile required; no rails/custom geometry inference.

Capture.accept_grid and suggest_hole require exact candidate/frame binding.
Acceptance derives independent strip label mapping from explicitly reviewed
printed corner labels, increments revision, clears circuit review and binds server
review to proposal digest. Ambiguous/outside/nonfinite touches cannot establish
connections. Restore validates binding; frame changes remove acceptance.
Workflow.accept_grid internally checks owner/lab/student, session/candidate state
and versions, persists with CAS and clears stale readings/diagnosis/checks.

Public API1.1 OpenAPI remains exactly equal to saved schema; no new HTTP events
or routes. Existing MP4/image-field/nested-payload/close flow remains unchanged.
Internal acceptance/suggestion is NOT wired to Android HTTP; actual overlay,
letterbox/zoom inverse and explicit alignment/label approval UI plus agreed mobile
transport are still needed. Until then use existing physical-hole manual correction.
No provisional hole labels are confirmed automatically. ML3 receives unchanged
diagnostic object, with complete-result equality regression and branch probes.

Verification:338 release tests pass, zero failures/skips (includes real synthetic
MP4 grid extraction, unsupported/blank fallback, label reversal, malformed geometry,
restore/tamper, ownership and actual concurrent session-version rejection).
Existing backend demo completes; originalManit uses labelled probability-safe
fallback, backend ML3 normaltemplate; pip check/diff check pass. No real capture
accuracy claim, live providers/product datapacks/credentials/Android/deployment
tested. Wheel build/module inspection passed; matching build summary saved and
new consumer decisions promoted successfully to gitgood-build.
Guide docs/ML2_AUTO_GRID_INTEGRATION.md; next review/commit and coordinate Android
controls/transport without changing required existing fields. No push/deploy.

## Public backend grid/wire integration completed (2026-11-01)

User steered work directly to backend/android-connection-test, requested integration
verification and necessary API changes; deployment/push from earlier request not
continued. Earlier saved files had already been restored before interruption.
This task made no further stash operations, branch switching, commits or pushes.
Fetched current sources: ML1 Abhiram d335af7 adds Android handoff docs over ea67b52
runtime; ML2 origin/tanu370759b contains shared grid implementation. Inspected
latest shared/promoted handoff and actual code. Shared core source matches tanu
ignoring CRLF; media.py adds only dismissal-flag cleanup on accept/frame changes.

Previous blocker superseded: grid acceptance is now public. Owner ML2/backend
Codex implementing user request. Additive API1.1 extension grid-review-1 discovered
via authenticated capabilities. Existing JSON create, MP4 /image field image,
expected_session_version, nested payload, states and close_session stay compatible.
New typed events: accept_grid, reject_grid, tap_endpoint, add_wire, remove_wire.
Read-only POST /api/v1/sessions/{id}/grid/suggest returns version-bound unconfirmed
suggestions without writes. Grid operations bind candidate revision, selected F-ID,
image SHA and board fingerprint; map is derived server-side after explicit label
and alignment acknowledgement. Wire creation needs two unambiguous native-pixel
taps and explicit same-physical-wire acknowledgement. Occupancy and duplicate IDs
checked. Reject restores manual path. Existing final confirmation remains separate.

New operations use durable event replay/atomic transaction ownership/lab/student
and stale-version gates. Asset reads reuse transaction connection. Edits invalidate
review/diagnostic and clear readings/checks/source settings; analog expectation
object shape retained (release suite caught and corrected a reset regression).
ML3 gets the existing diagnostic unchanged. No frame-selection or approved wire-only
experiment introduced; draft wire-hole exercise still not a backend catalog entry.
AUTO_GRID_ENABLED remains opt-in; board profile must match actual rows/geometry.

Contract docs/BACKEND_GRID_API.md and regenerated schemas/backend-openapi.json,
main API/Android/deployment guides, README and Kotlin preview reference updated.
ML1 docs/ANDROID_WIRE_REVIEW_HANDOFF.md imported with current backend extension note.
Android still must implement overlay, native-coordinate transforms, label approval
and wire-edit UI using published contract; no actual app source/build changed.

Verification:343 tests passed, zero failures/skips. Public MP4->preview->accept->
wire add/edit/remove->circuit confirm->ML2/ML3->close path passed; replay/conflict,
stale frame/profile/revision, ambiguity/invalid coordinates, occupancy, auth/ownership
and manual fallback covered. Both tools/demo_backend.py and --grid completed;
new transcript outputs/backend/synthetic-grid-transcript.json. Actual local uvicorn
boot /health200, /openapi.json200 registers new route. /ready503 local missing
Firebase project/credentials and enabled vision config; approved_real_experiments0.
No real OAuth/model/provider/Android-device/Render test or product datapack access.
Branch probes preserve strict-Manit labelled probability-safe fallback and normal
backend template, diagnostic unchanged. pip check/diff check and schema/doc checks
passed. Full suite last343; demos run separately after their CLI extension.
Next review/commit backend, configure real catalog/secrets and enable AUTO_GRID
for matching board profile, deploy and verify live readiness/device flow.
Matching summary saved; public grid-review-1 contract promoted successfully to gitgood-build.
# Wire-only backend/ML2 workflow (2026-11-01)

User requested immediate publication and integration. Work remains on
backend/android-connection-test; no stash, branch switch, commit, push or deploy.
Owner ML2/backend Tanu, implemented by Codex. Breadboard Wire Connections is now
in backend/catalog.json as wire-hole-practice-v1 version1, engine wire_connections.
Supersedes earlier notes saying no wire-only catalog/workflow exists.

Trusted board capture_mode enables empty components/ports only for wire mode;
normal circuits remain strict. Dedicated reasoning/wires.py handles reviewed
hole pairs, missing/extra wires against approved references, unordered matching
and distinct exact-hole vs strip-pair comparison. Unknowns/alternatives/unreviewed
observations block evaluation. No source/measurement/behavior simulation required.
Media receipt and grid-review guards retained; no references passed to ML1 and no
fake components. Generic Gemini component extraction disabled for wire exercise;
automatic grid plus explicit student pairing and final confirmation remain.
ML3 diagnostic schema2.0 and public Android routes/envelopes unchanged.

Workflow published for observations; sample expected wire pairs remain draft.
Until instructor/backend reference approval, results list reviewed pairs without
judging correctness. Draft does not satisfy production approved-reference check.
Android must permit empty parts/ports and skip source/measurement screens for this
engine. AUTO_GRID_ENABLED=true enables taps; actual board must match30rowprofile.
Custom EXPERIMENT_CATALOG_PATH requires adding the record to that catalog too.
Contract docs/BACKEND_WIRE_WORKFLOW.md; team decision saved/promoted to gitgood-build.

Seven focused tests pass including actual synthetic MP4 public HTTP workflow,
ML2/ML3 explanation and close, response/reference JSON schemas, ambiguity,
occupancy, wrong row, same strip/different hole, empty board and draft handling.
tools/demo_backend.py --wire-only completes, saves
outputs/backend/synthetic-wire-transcript.json. Final release suite:350 tests pass,
zero failures or skips (outputs/wire-final-checks.txt); git diff --check passes.
initial suite found an analog dispatch import collision (fixed), schema test found
missing diagnostic metadata (fixed). Live Render/Android/model accuracy untested.
README changed concurrently outside this task; those edits preserved.

## Backend branch consolidation verified (2026-11-01)

User requested merging backend, Abhiram, tanu and Manit. Fetched origin; started
from clean pushed backend54786ed. Remained on backend/android-connection-test.
Actual merge commits:3329676 includes Abhiram d335af7;3c2e55c includes tanu370759b;
5bdd09f includes Manitc084375. All three tips verified ancestors; no unresolved
index entries/conflict markers. No stash, source branch updates, main/Android
merge, push or deployment performed.

Reviewed conflicts preserve backend wire-only validators, size/revision guards,
video/grid review cleanup, public API1.1 and optional-probability ML3 compatibility.
Runtime backend/reasoning/labvision/mentor files unchanged from54786ed because
source implementations were already imported; merges add remaining source tools,
training fixtures, reports/docs and original tests. Preserved latest README and
AGENTS workflow, broader ignore rules plus ML3 local environment patterns.
Merged branch-specific context/plans are historical; this context.md and current
backend contract docs are authoritative. Resolution guide docs/BRANCH_INTEGRATION.md.

Added optional training-test dependency (torch), installed locally, and updated CI
and README so combined release tests run without skips. Production dependencies
unchanged. Verification:485 tests passed, zero failures/skips, exit0 via
python tools/run_checks.py; outputs/merged-release-checks.txt records results.
Synthetic MP4 wire demo closes successfully; strict originalManit yields labelled
probability-safe fallback and merged backend normal template; both keep diagnostic
unchanged without fabricated probabilities. pip check passes; conflict scan clear.
No real provider/auth/phone/Render/Docker validation in this merge task.

Integration ownership/branch decisions saved and promoted to gitgood-build.
Next push reviewed backend merges, then separately consolidate main/Android and
perform configured deployment/device verification. Local verification summary
synchronized to build memory; no product datapacks accessed.

## Main and neha consolidation (2026-11-01)

User requested all integrated work on main and neha. Refreshed origin/neha3b956d6
with latest Android parsing/grid fixes. Main92ac6ad merges backend0ae9cc9;
main6123246 joins unrelated Android history without rewriting either branch.
README conflict preserves Circuitly branding/current setup; .gitignore combines
backend and Android rules. App source remains identical to fetched Neha branch;
backend/ML runtime remains identical to verified backend0ae9cc9. README now covers
root Android Gradle project; .dockerignore excludes Android/cache artifacts.

No API changes, stash, push, deployment or credential/product-memory access.
Android test/build attempted: Windows wrapper mangles non-ASCII path; direct JAR
with workspace cache downloads Gradle but native SystemInfo service fails before
compilation on Java26. Installed Android SDK36.1 also does not satisfy requested37.
Android APK/device checks remain unverified. Final Python release check:485 tests
passed, zero skips/failures, exit0 (outputs/main-release-checks.txt). Backend runtime
and Android sources verified unchanged from their respective integrated tips;
all five source tips are ancestors. Local neha will fast-forward to this main
commit, preserving all history. No remote branches advanced. Build-memory summary
synchronization recorded for this follow-up.
