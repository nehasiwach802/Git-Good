# Backend branch consolidation — 2026-11-01

Integration target: `backend/android-connection-test`, starting at `54786ed`.
The fetched source tips are Abhiram `d335af7`, tanu `370759b`, and Manit `c084375`.
Each is recorded as a merge parent, rather than only copying files between branches.

| Source | Resolution |
| --- | --- |
| Abhiram / ML1 | Existing runtime already integrated. Added remaining training/evaluation tools, documentation, fixtures and tests. Kept backend size/revision guards and wire-only validation. Fixture JSON differences were formatting only. The conflicting ML1 handoff tests already exist as `test_ml1_handoff.py`; kept the distinct ML2 `test_handoff.py`. |
| tanu / ML2 | Shared media/grid/bridge implementation already integrated. Retained newer backend wire dispatch, grid-dismissal cleanup, backend packaging and public HTTP tests. Kept current transport documentation over older internal-only handoff notes. |
| Manit / ML3 | Service/memory/transport implementation already integrated. Added remaining original docs, launch helper and tests. Retained backend `mentor.py` support for explicit ordinal evidence when calibrated probabilities are unavailable. |

Backend README, AGENTS.md and living context.md remain authoritative for the
combined checkout. Imported branch-specific plans/reports and `context (1).md`
are historical artifacts, not replacements for current API documentation.
The broader backend ignore rules remain, with ML3's `venv/` and `.test-deps/`
patterns added. The existing MP4 route, nested event envelope, wire exercise,
Firebase authentication and review/version guards are preserved.

The combined release suite includes optional ML1 training tests. Install
`.[backend,test,training-test]` to run them all; `training-test` installs PyTorch.
CI includes this extra. Production backend dependencies do not include PyTorch
unless an operator separately enables a detector/training configuration.

All merges are local until pushed. The individual source branches, `main`, and
Android branch are not advanced by this backend consolidation. Deployment and
real-device/provider checks remain separate from local integration verification.

Verification: 485 tests passed with zero skips/failures using tools/run_checks.py
(exit 0). The synthetic MP4 wire demo completes. Original-Manit and integrated
ML3 probes preserve diagnostic facts and never fabricate probabilities. pip check
passes; all three source tips are ancestors; no unresolved conflict entries or
markers remain. Log: outputs/merged-release-checks.txt (local, ignored).
