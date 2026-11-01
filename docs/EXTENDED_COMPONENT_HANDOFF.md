# Op-amp and rectifier-diode observations

ML1 can now capture `opamp` functional terminals `+`, `-`, `out`, `vcc`,
`vee`, and `diode` terminals `anode`, `cathode`. Available in manual annotation,
upload fallback and the vision response vocabulary. This is representation
support, not newly trained component recognition. Exact physical package mapping
must be verified against the actual part; no universal op-amp pinout is assumed.

Candidates containing either new part must be fully reviewed before calling
`labvision.handoff.reasoning_input`. They use existing `internal_v1`, including
hole-only candidates, because the older `ml1_v0.1` adapter has fixed aliases.
Original candidates without these parts retain the existing adapter behavior.

Exports map opamp to `OPAMP` and diode to `DIODE`. Properties remain empty and
unconfirmed: ML1 cannot observe an ideal open-loop gain from a photo or invent
a diode model. Existing ML2 registry snapshot requires OPAMP gain for its model;
trusted explicit model configuration is still needed before simulation. DIODE
is absent from that snapshot and remains an explicit unsupported-model gap.
Do not substitute LED, a wire or an ideal short for a rectifier diode.

Validation: 85 tests pass. Actual saved ML2 parser at
outputs/team-contracts/ml2-02d4e36 accepts the two-part reviewed observation via
internal_v1 and reports DIODE in unsupported_models_preserved. This verifies
parser compatibility only, not current deployment or analog behavior.

Backend consumers should call reasoning_input instead of hardcoding ml1_v0.1
for every candidate. No backend routes, Android code or teammate registry was
modified. Update those consumers through their existing integration workflow.
