# Responsibility 2: cross-student equipment aggregation

`equipment_flags.py` is a deterministic module with no network calls, database,
LLM, or Meko reads. The application backend passes a structured snapshot of
equipment evidence; the module returns JSON-compatible review candidates.
It never publishes student claims as shared warnings. Approval, expiry, repair
retirement, and instructor UI belong to responsibility 3 and shared backend work.

## Run the simulated demonstration

```powershell
py -3 demo_equipment.py
py -3 -m unittest discover -s tests -v
```

Two students produce no flag under the default policy. Three students across
RC and op-amp experiments report outputs 50% below predictions on scope-3 CH2:
the module produces a `pending_review` candidate with their supporting session
and evidence IDs. Replaying an observation keeps the session count at three.
All demo data is visibly simulated and never sent to Meko.

## Backend / ML 2 contract

Construct `EquipmentEvidence` for a measured quantity, or use
`EquipmentEvidence.from_outcome(...)` with the responsibility-1 `SessionOutcome`.
The bridge selects a measurement by index. ML 2 supplies the expected value,
positive absolute tolerance in that measurement's unit, and deterministic
`netlist_matches_reference`. The backend supplies authenticated pseudonymous
student identity, lab identity, stable evidence/session/equipment IDs, and an
aware timestamp. Do not trust those fields directly from an unauthenticated client.

`metric` is a canonical identifier for comparable measurement conditions: peak,
RMS, and peak-to-peak readings must use different metrics. If settings affect
comparability, include the setting category in that canonical metric. This
module cannot infer probe attenuation, operating mode, or verified measurements
from a photo or free-form text. Those checks belong to ML 2 and the lab workflow.

Call `flag_equipment(evidence, as_of=aware_datetime, policy=FlagPolicy(...))`.
The default demo policy chosen by Codex is:

- At least 3 distinct sessions, 3 distinct students, and 2 experiments.
- Same lab, equipment, channel, metric, compatible unit dimension, discrepancy
  direction, and simulated/real mode. Simulated and real evidence never combine.
- Only confirmed, reference-matching circuits, with readings outside tolerance.
- Normalized discrepancy = `(observed - expected) / max(abs(expected), tolerance)`.
  A cluster's maximum minus minimum discrepancy must be at most 0.15. Example:
  -0.50 and -0.45 are similar; -0.50 and -0.10 are not. This is a configurable
  heuristic, not a learned probability. Zero expected values use tolerance as
  the normalization scale and need domain review before production use.
- Evidence within the last 7 days, inclusive, and no future timestamps.

Supported units are V/mV, A/mA, and Hz/kHz. Relative discrepancies are invariant
under these unit scalings. Candidate `unit` is the base unit; each supporting
reading retains its actual unit. Unknown units are rejected.

## Output and evidence handling

Each candidate contains `flag_id`, `status="pending_review"`, equipment/channel,
metric, discrepancy range, session/student counts, experiment IDs, simulated
label, policy, evaluation timestamp, and supporting sessions with evidence IDs,
expected/observed values, units, tolerances, and observation timestamps. There is
no fault probability or approval claim. Student identities are used internally
for independent counts and are omitted from the returned support records.

Exact observation replays are ignored. Conflicting reuse of an evidence ID is
rejected. Multiple readings in one student's session count as one supporting
session in each candidate. Input order does not affect output. Maximal similar
windows are used so a distant outlier does not hide a valid cluster; overlapping
patterns can yield multiple candidates. A candidate ID is stable for the same
equipment signature and supporting evidence IDs, and changes when support changes.

The caller owns authoritative evidence storage, access control, and scheduling.
Re-evaluate from the current snapshot after a correction or deletion rather than
appending a second conflicting version. Deduplicate review queue submissions by
candidate ID; grouping revisions into one continuing equipment incident belongs
to the later lifecycle layer. Backend integration with that queue is still needed.

Do not aggregate by searching every student's private Meko datapack: use authorized
structured equipment observations from backend session records. Personal memory
and equipment evidence have separate purposes. Before production, validate the
thresholds with real lab incidents and have the team agree on canonical metrics.
Repeated anomalies are grounds for instructor investigation, not proof of a fault.
