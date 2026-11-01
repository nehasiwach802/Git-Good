# Retraining after user review

2026-11-01. User completed 15 seed frames, containing 148 endpoint regions.
Coordinates changed on 11 frames. Crowded video-07 remains excluded. Hashes,
review provenance, coordinate bounds and duplicate coordinates were checked.

Dataset: `outputs/endpoint-dataset-reviewed-v2`. Nine reviewed training images,
two validation and four evaluation images; plus 152/26/22 synthetic images.
No unreviewed pseudo labels included. Physical layout independence remains
unverified, and evaluation frames were already seen during development.

YOLO11n was fine-tuned from the same official pretrained checkpoint for 30
epochs, taking 277.52 seconds. Checkpoint:
`outputs/endpoint-train-reviewed-v1/fit/weights/best.pt`.
SHA256: `69cc10dfface53a1f2ffa4df530ec24da198c13406537826c1473d500f1e2711`.

Both models evaluated against the same corrected four-frame development set:

| Metric | Original pilot | Reviewed-label retraining |
| --- | ---: | ---: |
| mAP50 | 0.5381 | 0.5465 |
| mAP50–95 | 0.1754 | 0.1776 |
| Precision | 0.5861 | 0.6006 |
| Recall | 0.5500 | 0.4750 |

Precision/recall are the evaluator's selected operating points, not a fixed
shared confidence threshold. Synthetic mAP50 remains approximately 0.992.
This is a mixed result, not an established improvement or generalization claim.
Keep both checkpoints; no production/default model was replaced.

Raw evaluations: `outputs/endpoint-eval-reviewed-baseline-v1/evaluation.json`
and `outputs/endpoint-eval-reviewed-new-v1/evaluation.json`.
Video previews: `outputs/endpoint-predictions-reviewed-v1/` (confidence 0.5,
retained from the previous pilot, not tuned on these evaluation results).

All predictions remain unreviewed proposals. No hole assignment, wire pairing,
multi-view fusion or circuit connectivity is provided by this detector.
Next useful validation is on independently captured layouts; more epochs alone
are not justified by this comparison. Existing backend/Android/ML2 unchanged.

Validation: 80 tests passed; modified training/data/evaluation scripts compiled;
training and both evaluation processes exited successfully.
