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

## Latest verification

Last executed during repository initialization on 2026-10-31:

- `python -m reasoning examples/rc.json --validate-only`: passed.
- `python -m unittest discover -s tests -v`: 28 tests; 27 passed, 1 skipped.
- Skipped: real ngspice integration because ngspice is not installed/on PATH.
- `git diff --check`: passed; Git reported a line-ending conversion warning.
- CI workflow exists for Python 3.11/3.14 with ngspice on Ubuntu; remote execution
  has not been verified. Mock adapter tests do not prove live solver accuracy.

## Blockers and next steps

1. Install/locate ngspice and run real RC/op-amp integration tests.
2. Agree on final experiments, physical device models, source conditions and
   required analyses. Existing RC/op-amp JSON files are simulated fixtures only.
3. Agree with ML1 on component identity, connection uncertainty and image evidence;
   keep current component-level confirmation until an extension is agreed.
4. Finalize instructor-approved probes/checks, measurement conventions/tolerances,
   equipment metadata and ML3 evidence semantics.
5. Integrate with Android/shared backend and define deployment, authentication,
   session storage and retention.

Current limits: ideal op-amp excludes rails/clipping; no DC/transient/phase modes,
calibrated probabilities or calculated information gain. Ambiguous wiring cannot
always be localized. No vision, product memory integration or persistent backend
store is implemented here.

## Context maintenance and Meko

File-change overview lookup title: `Git-Good file changes summary - 2026-10-31`.
Save the overview as ordinary memory under `codex:Git-Good` in `gitgood-build`;
do not promote that overview out of memory. Promote teammate-facing decisions
separately. The overview includes modified tracked files and untracked additions,
which `git diff --stat` alone does not show. It summarizes working-tree work, not
a committed release. Latest test counts above are historical, not rerun for this
documentation/memory update.

Follow [AGENTS.md](AGENTS.md) before and after every task. Refresh this file when
state changes, save a matching concise summary to `gitgood-build`, and promote
changed teammate-facing decisions with their owner. Recall may return older
information; reconcile with the checked-out repository and latest actual checks.

Synchronization is performed by the coding agent during tasks, not by a running
background service. If Meko fails, record pending synchronization here and retry
on the next task. Never access product datapacks or store secrets, personal data
or raw student sessions in this context or the build datapack.
