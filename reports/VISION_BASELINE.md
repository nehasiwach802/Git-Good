# First automatic endpoint development check

The first photo has a user-reviewed connectivity export, not a proven-correct
circuit. Its saved session and netlist both use revision 45 and recompile to
exactly the same output. The supply-routing concerns in
`FIRST_REAL_NETLIST_REVIEW.md` still apply.

## Real-data package

`outputs/real-dataset-v1/` contains the original image, a partial label record,
the reviewed netlist and a manifest. There are 18 visible labelled physical
endpoints and 14 unlabelled/unknown-visibility positions. Human-reviewed visible
proposals are accepted using the matching reviewed netlist as evidence. The
import rejects mismatched revisions, changed coordinates or different topology.
Pose-derived hidden pin locations never become fabricated visible pixel labels.
The one assembly has `split: unassigned`; this is not a train/test dataset yet.

## Gemini pixel request

`tools/predict_wire_pixels.py` sends only a photo crop and a wire-localization
prompt, not reference endpoints, wiring, calibration or expected hole IDs.
The model is asked for normalized [x,y] coordinates and pairing uncertainty.
Requests have bounded timeouts and preserve sanitized failure metadata. They do
not automatically retry. Keys are read from the existing .env loader and never
printed or included in output metadata.

The network-enabled wire request timed out after 45.12 seconds. A separate
minimal image-description probe also timed out. No successful model prediction
was obtained in this run; these timeouts do not measure image accuracy or
establish the cause of the failure. Results are under `outputs/pixel-baseline/`.

The adapter follows Google's documented [image input](https://ai.google.dev/gemini-api/docs/image-understanding)
and [structured JSON output](https://ai.google.dev/gemini-api/docs/structured-output)
interfaces. Documentation support is not evidence of runtime availability.

## Local baseline

`labvision/localvision.py` thresholds saturated red pixels, thins the mask,
finds skeleton tips and extrapolates them toward calibrated central-grid holes.
It has no trained weights, component detector or wire-pairing implementation.
All output stays unconfirmed and uncertain.

The predictor receives photo pixels, board geometry and calibration. Reference
endpoint labels are collected only afterwards for scoring. Sparse user-added
rail contacts reveal annotated locations, so rail holes are deliberately excluded
from prediction and headline scoring. This leaves 7 visible central-grid wire
endpoints in the reviewed reference. Component pins and external clips are not
included in these metrics.

| Minimum branch length | Matched | Proposals | Reference | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| 3 | 4 | 23 | 7 | 17.4% | 57.1% |
| 6 | 3 | 12 | 7 | 25.0% | 42.9% |
| 10 (default) | 2 | 4 | 7 | 50.0% | 28.6% |

These are development measurements on the same image inspected while choosing
the color threshold. They are not held-out accuracy or evidence of generalization.
Glare and wire crossings create false tips and hide real ends. Relaxing the
branch threshold raises recall while sharply increasing incorrect proposals.
The baseline is not ready to auto-label a complete circuit. It does not change
the reviewed user files.

Artifacts: `outputs/local-baseline/primary-v1/` contains the mask, skeleton,
proposal JSON, overlay and evaluation JSON. The parameter comparison is saved
separately in `outputs/local-baseline/development-parameter-check.json`.

## Reproduce

Install the optional local dependencies with
`python -m pip install -r requirements-local-vision.txt`, then run:

```powershell
python tools/run_local_baseline.py "ckt breadboard/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).jpeg" --session "examples/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).annotations.json" --reviewed-netlist "examples/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).netlist.json" --crop 175 530 739 1210 --out outputs/local-baseline/new-run
```

Use a new output directory; existing results are preserved. A bounded online
attempt is available with `tools/predict_wire_pixels.py --help`; `--dry-run`
prepares the crop without reading credentials or making a network request.

## Current usable scope

The demonstrated path is photo calibration, assisted/manual review and
deterministic connectivity export. Automatic predictions remain experimental.
Use the reviewed export for the ML2 interface/demo as an observed circuit,
with the supply inconsistency disclosed. Next evaluate an improved predictor
on an independently wired build. Keep related camera views in the same split;
do not claim model training or automatic graph accuracy from this one example.
