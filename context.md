# Git-Good project context

Last updated: 2026-10-31 (Asia/Calcutta).
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

Latest verification during actual ML1 integration on 2026-10-31:

- `python -m reasoning examples/rc.json --validate-only`: passed.
- `python tools/run_checks.py`: 80 tests passed, zero failed and zero skipped;
  includes real ngspice RC/op-amp, digital gate checks, candidate conversion,
  session boundaries, provider-failure mocks, CLI, HTTP and JSON Schema checks.
- Real solver testing exposed and fixed v(0) ground-vector handling. Degenerate
  circuits are rejected; differential/zero readings are tested.
- `python tools/demo.py`: all four synthetic scenarios produced expected checks;
  RC prediction 0.707106781 V; 7400 truth table 0->1 and 1->0.
- `git diff --check`: passed; Git reported a line-ending conversion warning.
- CI workflow exists for Python 3.11/3.14 with ngspice on Ubuntu; remote execution
  has not been verified remotely. Provider mocks do not establish photo accuracy.

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
5. Integrate with Android/shared backend and define deployment, authentication,
   session storage and retention.

Current limits: ideal op-amp excludes rails/clipping; no DC/transient/phase modes,
calibrated probabilities or calculated information gain. Ambiguous wiring cannot
always be localized. Digital mode is isolated 7400 NAND-as-NOT only, without TTL
voltage/timing/loading or device-health simulation. Vision extraction code is
present but no paid/live extraction ran for integration. Product memory integration,
Android orchestration, authentication and persistent backend storage remain outside
this implementation. Software tests cannot prove every possible physical fault.

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
