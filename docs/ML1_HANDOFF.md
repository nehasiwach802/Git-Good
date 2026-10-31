# ML1 handoff: draft v0.1

Implementation owner: ML person 1, developed with the coding assistant. This local format is implemented and ready for teammate review; it is not a team-ratified backend API. The digital experiment is an initial prototype selected from the 7400 hardware discussion, not a replacement for the entire project scope.

## Entry points

All functions accept JSON-compatible dictionaries and raise `CandidateError` for invalid candidates:

```python
from labvision.core import validate, pending, correct, confirm, compile_netlist
from labvision.vision import extract

candidate = extract(image_path, board, model=available_gemini_model_id)
review_items = pending(candidate, board)
candidate = correct(candidate, board, "U1.1", "E10", expected_revision=1)
# Call only after the student has actually reviewed ALL observations and omissions.
candidate = confirm(candidate, board, expected_revision=2)
netlist = compile_netlist(candidate, board)
```

There is no HTTP service or Android review UI in this milestone. Integrate these functions into the team's backend after agreeing its authentication/session model. The CLI is a local review/development interface.

## Candidate observations

See `examples/7400-not.candidate.json` for the full runnable fixture. Version is `0.1` (not the earlier planning document's illustrative `0.1-draft`). Components use `part` rather than the planning sketch's `type`. These are explicit draft implementation choices to discuss with ML person 2.

- `candidate_id`, positive `revision`, `board_profile_id`.
- `board_confirmed` and `reviewed_revision`: only human review grants these. Correction increments revision and clears whole-circuit review.
- `components`: ID, supported part, identity/orientation review, physical pin map. Resistor/capacitor values are positive SI numbers and require separate confirmation.
- `wires`: ID and independent `a`/`b` endpoints.
- `ports`: ID, role (`input`, `output`, `vcc`, `gnd`), endpoint. A port is a logical tap, so it may refer to an already occupied hole.
- Every endpoint has `hole` (or null), alternative holes, confidence (`likely`, `uncertain`, `unknown`), reason, source and confirmation flag. Labels are uncalibrated. Confirmation may accept a resolved observation originally marked uncertain.
- `issues`: evidence/limitations for review. They are advisory strings, not a machine-validated assertion that a circuit is complete. Review must resolve omitted or unsupported objects by editing observations or marking the capture unsupported.

Schema validation requires the full pin set for each supported component. `7400` currently refers only to the confirmed 14-pin DIP logical model; it does not claim all package/family variants are interchangeable. Hidden pin holes remain null until corrected. Unknown component types fail validation instead of being simulated as another part.

Only endpoints with different physical holes may coexist; two inserted leads cannot occupy the same hole. Points in one internally connected strip still share a node. Candidate edits other than the `correct` function (adding/removing components, entering values, changing identity or ports) are currently manual JSON edits: increment `revision`, set `reviewed_revision` to null and clear affected confirmation flags. Do not edit an exported netlist and call it a reviewed revision.

## Board profile

`groups` explicitly lists each group of internally connected hole IDs. Generated profiles have A–E and F–J strips at each row and deliberately omit rails. This is a demo convention, not a confirmed map of the photographed board. Verify printed letters, numbering, orientation and actual rail breaks on the physical board.

To support power rails, add their real hole IDs in separate groups for each electrically continuous segment. Never join opposite rails or split segments by color. Real board calibration and automatic perspective/grid detection are not implemented yet; the model currently proposes printed hole IDs directly.

## Export to ML person 2

`compile_netlist` exports:

- `status: reviewed_connectivity`, source candidate/revision and board ID.
- Components with physical pin names mapped to electrical node IDs.
- Ports mapped to nodes and a node-to-hole map.
- Endpoint provenance, extraction caveats and explicit limitations.

Only board strips and jumper wires merge nodes. Passive components and IC pins remain distinct terminals. Node IDs are deterministic within the candidate's connectivity but are not comparable labels across builds or revisions. Use graph equivalence/component semantics for reference comparison.

Reviewed wrong wiring is exported unchanged. Supply shorts, missing supply connections and wrong connections are observations for the reasoning engine, not schema failures. `reviewed_connectivity` means review is complete, not that hardware is safe or circuit behavior is correct. It does not guarantee analog simulation readiness, device models or configured supply values.

## Local reference check

`labvision.digital.check_not` validates an isolated 7400 gate used as an inverter, with explicit input/output/VCC/GND ports. It reports structural mismatches and unused-input warnings, and returns the ideal two-row truth table only when the selected topology matches. Additional circuit components are refused by this limited check. It is not ML person 2's full graph diff, simulator, hypothesis ledger or equipment diagnosis.

Reference pinout and logic: [TI SN7400 datasheet](https://www.ti.com/lit/ds/symlink/sn7400.pdf), 14-pin package top view, sections 5 and 6.3. The source experiment is draft pending instructor review.

## Gemini integration

Uses the official `generateContent` REST endpoint with inline JPEG/PNG and JSON output schema. The extractor automatically reads `GEMINI_API_KEY` and `GEMINI_MODEL` from the project-root `.env`. Existing process environment variables take precedence; `--model` overrides the model setting. The dependency-free loader accepts plain/quoted values and optional `export`, without executing shell commands or expanding variables. There is no default model because available IDs/access vary. Keys are never printed or written by the application; the user-managed `.env` is excluded from Git.

Images are sent to Google's API only when `extract` is invoked. Inputs are capped at 10 MB, requests time out, and incomplete/blocked/malformed provider outputs fail explicitly. Credentials use the request header, not URL parameters. A failed request leaves the manual JSON path available; no extra paid retries are automatic.

The extraction prompt receives observed image and board/catalog context, without the experiment reference wiring or truth table. Never pass the instructor's reference wiring into the extraction stage. All model-supplied human-review flags are reset to false. A model may still guess holes or omit wires: full student review and an independent labelled-photo evaluation remain required.

Sources: [Gemini image input](https://ai.google.dev/gemini-api/docs/generate-content/image-understanding), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [REST configuration](https://ai.google.dev/api/generate-content).

## First real-photo run

See `reports/7400-photo-first-run.md`. A short image probe succeeded, but full
extraction attempts timed out and the final compact request returned HTTP 503.
No real-photo netlist or accuracy claim has been established. The adapter now
accepts optional timeout, raw-response path, supported thinking level and a list
of student-reported part identities. The CLI also has a `report` command for
Markdown endpoint review sheets. These additions do not change netlist schema
v0.1 or permit model self-confirmation.
