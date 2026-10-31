# First real-photo run: 7400 breadboard

Date: 2026-10-31. Source: the supplied 7:04 PM circuit photograph.

## Result

**Basic image input works, but a complete structured extraction was not obtained.**
The image-only probe returned HTTP 200 and described an illuminated red LED and an
integrated circuit on a solderless breadboard. This is component-level evidence,
not verification of chip markings, pin locations, connections or NOT behavior.

The user identified the IC as 7400. The probe was not given the intended wiring.

## Requests made

| Attempt | Request | Observed result |
|---|---|---|
| 1 | Full extraction, original schema, 45-second timeout | Timed out / no provider result |
| 2 | Full extraction, original schema, 180-second timeout | Timed out / no provider result |
| 3 | Full extraction, compact hole schema, low thinking, 180-second timeout | Timed out / no provider result |
| 4 | Short image-only probe, low thinking | HTTP 200; component description returned |
| 5 | Compact endpoint records, student-reported 7400 identity, low thinking, 120-second timeout | HTTP 503; service unavailable |

An initial sandbox-blocked attempt did not reach Google. Network-enabled attempts
were explicitly approved. There is no reliable information on whether timed-out
requests consumed provider tokens; do not assume they were free or completed.

## Artifacts

- `outputs/7400-photo.vision-probe.json`: actual image-only provider response.
- `outputs/7400-photo.board.json`: provisional 63-row terminal-strip profile,
  excluding rails. This is a configuration assumption, not a measured board map.
- `outputs/7400-photo.manual-template.json`: manual annotation scaffold, explicitly
  labelled as a fallback. It is **not Gemini extraction output**.
- `outputs/7400-photo.manual-review.md`: review sheet for that manual scaffold.

No model-generated candidate netlist or verified student circuit was produced.
No photo-derived endpoint was marked confirmed, and no diagnosis of the physical
circuit was made. The synthetic example remains separate from this real capture.

## Software improvements from the run

- Configurable request timeout, capped at 300 seconds.
- Optional local raw provider-response capture for successful HTTP responses,
  including extraction results that subsequently fail validation.
- Optional model-supported thinking effort and student-reported part identities.
- Smaller JSON response schema without repeating every possible hole ID. Local
  validation still enforces the board's allowed holes.
- Compact endpoint records with uncertainty; missing reasons/alternatives receive
  explicit defaults and all model observations remain unreviewed.
- Markdown review-sheet command listing endpoint proposals and unresolved checks.
- Short image-only diagnostic mode, independent of the extraction schema.

## What remains

Retry structured extraction once the provider is responsive; the final HTTP 503
does not establish a schema or authentication error. Latency improvements have
not yet been shown to make full extraction reliable.

For verified wiring, obtain an overhead closeup with printed row/column labels,
the IC notch and every lead insertion visible, or enter exact physical pin/hole
assignments manually. The present angled photo cannot independently establish
all hidden endpoints or the board's rail topology. Verify LED connections and any
load components rather than assuming illumination equals a particular logic level.

Command for a later retry from the project directory:

```powershell
python -m labvision extract "C:\path\to\breadboard.jpeg" --board outputs/7400-photo.board.json --known-part 7400 --thinking-level low --timeout 120 --raw-response outputs/7400-photo.provider.json --out outputs/7400-photo.candidate.json
```

Review the provisional board profile before accepting hole IDs from any retry.
