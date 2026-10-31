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

backend/app.py now provides authenticated API 1.0: experiment/capability lookup,
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
