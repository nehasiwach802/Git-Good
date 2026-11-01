# ML person 1: 18-hour implementation plan

Status: proposed implementation plan, not an agreed team API contract.
Owner: ML person 1. Budget: 18 hours from starting work.
Source: context.md. Hardware/photo availability remains unconfirmed.

Implementation update: a 7400 NAND-as-NOT local prototype now exists in
`labvision/`, using the hardware identified in chat. See `README.md` and
`docs/ML1_HANDOFF.md` for current commands, schema differences, synthetic fixtures
and limitations. Gemini access was confirmed by ML person 1; local key/model
configuration and real-photo evaluation are still pending. The original analog
experiment pair and full project scope have not been replaced by a team decision.

## Outcome

Given a photo of a supported breadboard, propose components and terminal locations, expose uncertain connections for student correction, and export a confirmed electrical netlist for ML person 2. Evaluate both the initial predictions and the corrected result on labelled photos.

Success means completing this flow on both demo experiments and reporting its actual limitations. Photo processing must preserve a student's wiring mistakes so the reasoning engine can detect them.

## Scope to settle in the first hour

- One physical breadboard model, with an explicit hole map and verified power-rail breaks.
- Top-down photos with the whole board visible, good lighting and little occlusion. Use four identifiable board points for alignment; allow manual selection when needed.
- Start with the RC filter. Retain the proposed inverting op-amp as the second experiment, subject to available hardware and ML person 2's model support.
- Record the exact component packages, op-amp pinout and supported component values. Values and chip identity can be entered or confirmed by the student.
- Support the component types required for those experiments first. LED recognition can follow if time permits; the broader library in context.md remains the eventual target.
- Ask the team to agree on the intermediate representation below before treating it as a shared contract.

## Architecture

1. **Capture and alignment.** Load the photo, validate its dimensions, identify four board landmarks and map it to the known board coordinate system. Show the aligned grid overlay for confirmation. OpenCV perspective transforms are suitable for this operation; board alignment does not by itself reveal hidden leads.
2. **Candidate extraction.** A replaceable vision adapter proposes component types, bounding boxes and individual pin/wire endpoints. Prototype with an available image-capable model or existing detector; provider, access and performance must be checked in hour 1. Avoid committing the deadline to training a new detector.
3. **Endpoint mapping.** Convert visible endpoints to candidate hole IDs. Store alternatives or an unknown endpoint when evidence is insufficient. A component bounding box alone is insufficient to establish electrical connectivity.
4. **Confirmation.** Student reviews the whole proposal, resolves unknown endpoints, corrects types/values and adds missed components. Manual input produces the same representation as vision.
5. **Connectivity compilation.** Merge holes connected by the board's internal strips and explicitly confirmed jumper wires. Each resulting group is an electrical node. Resistors, capacitors and ICs remain components between nodes; never merge their terminals as if they were wires.
6. **Handoff.** Export the reviewed components and their terminal-to-node mapping, external port assignments, provenance and revision. ML person 2 performs graph comparison and SPICE conversion.

Extraction receives the permitted component catalog and board profile. Keep the reference circuit's wiring out of extraction input so the model cannot silently replace observed mistakes with the expected answer.

## Proposed data boundary

Maintain two representations: observations in physical board coordinates and an electrical netlist derived from the reviewed observations.

Candidate record:

```json
{
  "schema_version": "0.1-draft",
  "candidate_id": "candidate-001",
  "revision": 1,
  "board_profile_id": "demo-board-v1",
  "status": "needs_confirmation",
  "components": [
    {
      "id": "R1",
      "type": "resistor",
      "value_si": null,
      "pins": {
        "1": {
          "hole": "A10",
          "alternatives": ["A11"],
          "confidence": "uncertain",
          "reason": "lead partly hidden",
          "source": "vision",
          "confirmed": false
        },
        "2": {
          "hole": null,
          "alternatives": [],
          "confidence": "unknown",
          "reason": "endpoint occluded",
          "source": "vision",
          "confirmed": false
        }
      }
    }
  ],
  "wires": [],
  "ports": [],
  "issues": []
}
```

This is a partial illustration, not a complete schema. Agree these additional details with teammates:

- Bounding boxes and endpoint coordinates normalized to the original image; preserve the alignment transform so Android can draw corrections accurately.
- Board profiles enumerate legal hole IDs and connected groups, including rail segments.
- Wires have two independently reviewable endpoints. Crossing wires do not imply a junction.
- External ports explicitly identify ground, signal input, output and supply connections. Never infer ground from wire color alone.
- IC pins use physical pin numbers and a confirmed part/model identifier. Orientation must be reviewed.
- Component values have SI units and their own source/confirmation state. Required unknown values block simulation-ready export.
- Confidence labels describe uncertainty, not calibrated probabilities. Numeric model scores, if retained, must be identified as uncalibrated.
- Exported nodes use deterministic IDs within a candidate revision. ML person 2 compares connectivity without assuming node labels or component IDs match the instructor reference.
- Any edit increments the revision and invalidates older confirmation/export results.
- Validation catches invalid holes, duplicate IDs, missing required pins, unresolved choices and invalid field types. Unexpected circuits remain valid observations for diagnosis; don't reject them merely because they differ from the reference.

## Proposed API operations

Integrate with the team's backend framework; exact routes and deployment remain open.

| Operation | Input | Output |
|---|---|---|
| Extract | Photo, board profile, allowed catalog | Candidate, image overlays, issues and confirmation items |
| Correct | Candidate ID, expected revision, edited observations | Validated next revision and outstanding issues |
| Confirm/export | Candidate ID, expected revision, review acknowledgment | Confirmed netlist or explicit unresolved-field errors |
| Manual create | Board profile and manually entered observations | Same candidate format as extraction |

Provide example request/response fixtures in hour 1 so Android and ML person 2 can proceed. Scope access to the owning session in the shared backend. Model credentials stay on the server. A provider timeout must return a recoverable failure that lets the student continue manually.

## Schedule and exit criteria

| Hours | Work | Exit criterion |
|---|---|---|
| 0–1 | Check hardware/photos, model access, board profile and draft contract with teammates | One real sample photo, known board topology, shared fixture or documented blockers |
| 1–3 | Implement manual observations, validation and connectivity compiler | Manually entered RC circuit exports correctly; ML person 2 can consume fixture |
| 3–6 | Align board; prototype candidate extraction on several real photos | Measured endpoint performance and a clear decision on automation scope |
| 6–9 | Add uncertainty, overlays, corrections and candidate revisions | Photo-to-reviewed-netlist works end to end for RC |
| 9–12 | Add second experiment/package support; integrate Android and reasoning | Both experiments use the same extraction/compiler interface |
| 12–15 | Evaluate on held-out photos; fix highest-impact failures | Results for raw extraction, corrections, fallback rate and latency |
| 15–18 | Freeze features, rehearse and repair integration issues | Repeatable phone demo plus usable manual/network-failure path |

At hour 6, if exact endpoint proposals remain unreliable, narrow automated capture conditions and rely on explicit endpoint correction. Continue to display real extraction results and measure the correction burden. Manual-only operation is a fallback, not proof that photo extraction succeeded.

If physical hardware or photos are unavailable, build the schema/compiler with labelled fixtures immediately and obtain real photos in parallel. Synthetic fixtures validate software logic; they cannot establish real-photo accuracy.

## Data and evaluation

Target 20–30 photos across both experiments if hardware and time permit. Include correct circuits, intentionally moved leads, crossing wires, occluded endpoints and moderately angled captures. Record the true component pin-to-hole assignments, values, ports and board profile for each physical build.

Split by physical circuit assembly/layout so near-duplicate photos of one build do not appear in both development and evaluation sets. Reserve several independent builds for final evaluation. Report sample counts; this small dataset is a demo assessment, not evidence of broad reliability.

Measure:

- Raw endpoint-to-hole accuracy, including unknown endpoints in coverage reporting.
- False confident connections and the fraction flagged for review.
- Exact electrical-connectivity match per circuit, ignoring arbitrary node labels.
- Component/pin detection omissions and type errors.
- Number of corrections, manual fallback rate, and time to confirmed netlist.
- Extraction latency, timeout rate and final confirmed-netlist correctness.

Proposed demo gate: every selected demo assembly must reach the correct reviewed netlist; unresolved required connections or values must never silently pass export. Report automated accuracy separately from reviewed accuracy. Student confirmation establishes the entered circuit model, not physical continuity or equipment health.

## Focused checks during implementation

- Breadboard strip connectivity, center gap and split rails follow the actual profile.
- Jumper wires merge nodes; resistors and capacitors do not.
- Crossing wires remain separate unless endpoints connect them.
- Missing ground/supply mappings and ambiguous required pins block ready-for-simulation status.
- Corrections recompute nodes and stale revisions cannot export.
- A wrong-but-confirmed wiring arrangement survives export unchanged.
- Both experiment fixtures and provider-failure/manual fallback work through the same interface.

## Coordination

- ML person 1 + ML person 2: agree netlist schema, terminal names, units, port semantics and error handling first.
- ML person 1 + Android: agree overlays, coordinates, corrections and manual entry early.
- ML person 3: receive confirmed revision/provenance through the shared backend; product memory remains their integration responsibility.
- Team: finalize experiment/hardware choices and continue the problem-validation work listed in context.md.

No new team-wide contract is finalized by this document. Record accepted decisions with their decision owner in gitgood-build when agreed. Coding agents must not access product datapacks.

Reference: OpenCV geometric transformations documentation, https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html .
