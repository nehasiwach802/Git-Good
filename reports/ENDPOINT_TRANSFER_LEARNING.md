# Wire-end region transfer-learning pilot (2026-11-01)

Follow-up: `reports/LORA_VISION_EXPERIMENT.md` documents the completed DINOv2 LoRA
experiment. It did not outperform this YOLO pilot in the preliminary comparison.

## Outcome

Fine-tuned official pretrained **YOLO11n** for 30 epochs on the RTX 4060 Laptop
GPU. This is transfer learning, not training from scratch. Training completed in
237.86 seconds using the isolated `outputs/training-env` environment with
PyTorch 2.11.0+cu128, torchvision 0.26.0+cu128 and Ultralytics 8.4.195.

Checkpoint: `outputs/endpoint-train-v1/fit/weights/best.pt`.
SHA256: `b2942301b590ca6bd8fd7a9d4214e34a51acb17630a866df02ac1581d007a191`.
Original pretrained checkpoint SHA256:
`0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.

The model proposes approximate **wire-end regions**, including loose ends. It
does not classify inserted versus loose ends, identify exact contacts or holes,
pair wires, recognize ICs, fuse calibrated views or produce a circuit netlist.
Predictions remain unreviewed; confidence scores are not calibrated probabilities.

## Supervision and splits

The original heuristic pass confused printed rail markings with wires. Those
96-frame heuristic datasets (v1/v2) were not used for this training run. Instead,
the assistant visually inspected seed frames and prepared **138 approximate
region proposals across 15 frames**. These remain AI pseudo labels, not human
ground truth. One crowded seed view (video-07) was excluded rather than treated
as an empty negative image.

| Data | Train images | Validation images | Test images |
|---|---:|---:|---:|
| AI seed proposals from videos | 9 | 2 | 4 |
| Stylized synthetic scenes | 152 | 26 | 22 |

All frames of a given video stay in the same provisional group. Synthetic groups
retain their original layout-based splits. Repeated layouts across distinct
videos still require review. All representative real images were viewed during
development; this is not a blind real-world benchmark. Other frames of a seed
video are not independent test images just because they were not used for fitting.

Training source: `outputs/endpoint-dataset-v3/manifest.json` with SHA256
`4c1327150f0e937d7d2c64d2a90a9ee9bb3d3c90819417fac96b00b7c554b91d`.
Model selection used the mixed synthetic/pseudo-label validation split.

## Evaluation

| Evaluation scope | Precision | Recall | Box mAP50 | Box mAP50–95 |
|---|---:|---:|---:|---:|
| Synthetic test scenes only | 0.992 | 0.976 | 0.992 | 0.791 |
| Agreement with unreviewed AI test proposals | 0.588 | 0.529 | 0.558 | 0.164 |

These are region-box metrics. The second row measures agreement with imperfect
AI labels; it is **not established real detection accuracy**. Neither row measures
hole assignment or electrical correctness. The substantial synthetic/real gap
is visible in previews: real frames contain false detections on printed markings
and missed wire ends. There is no measured single-image versus multi-view gain.

Raw results: `outputs/endpoint-evaluation-v1/evaluation.json`.
CPU inference processed all 96 selected frames from 16 videos in 17.482 seconds,
including rendering after model loading and excluding video decoding. See
`outputs/endpoint-predictions-v1/prediction-overview.jpg` and `predictions.json`.
The direct-MP4 command was also exercised successfully on a real supplied video,
selecting and predicting six frames in `outputs/endpoint-video-smoke-v1`.

## Reproduce

Use the separate GPU environment, not the existing global CPU-only PyTorch:

```powershell
python -m venv --system-site-packages outputs/training-env
outputs/training-env/Scripts/python.exe -m pip install torch==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
outputs/training-env/Scripts/python.exe -m pip install ultralytics==8.4.195
```

Original pretrained weights came from:
https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt

With the existing frame/synthetic artifacts and pretrained weights, use new output
directories when rerunning:

```powershell
python tools/build_endpoint_dataset.py --videos outputs/video-pilot-v2 --synthetic outputs/synthetic-v1 --seed-labels examples/video-seed-proposals.json --out outputs/endpoint-dataset-next
outputs/training-env/Scripts/python.exe tools/train_endpoints.py --dataset outputs/endpoint-dataset-next --out outputs/endpoint-train-next --weights outputs/pretrained/yolo11n.pt --epochs 30 --allow-pseudo-labels
outputs/training-env/Scripts/python.exe tools/predict_video_ends.py --video "path/to/video.mp4" --weights outputs/endpoint-train-v1/fit/weights/best.pt --out outputs/video-prediction-next --device cpu
```

Without `--allow-pseudo-labels`, the training script rejects an unreviewed real
dataset. Hidden synthetic endpoints are excluded. Image hashes bind seed labels
to the exact source frames. Training audits reject exact-image and known-layout
leakage across splits. No reference circuit wiring enters labeling or prediction.

## Next useful improvement

Review the small seed batch, correct misplaced regions, add missed ends, then
retrain. A local review tool supports dragging/adding/deleting points and explicit
completion per frame; any edit clears that frame's reviewed state. Original
proposals/photos are preserved. This checks wire-end regions, not hole labels.

```powershell
python tools/review_endpoint_seeds.py --seeds examples/video-seed-proposals.json --out outputs/reviewed-video-seeds.json
```

Before reporting real accuracy, obtain reviewed labels on additional held-out
layouts and capture sessions, and compare video against single-frame inference
using validated per-view board geometry. Keep this pilot out of automatic
connectivity decisions until those checks pass.

No Android, backend, ML2, deployed route or README changes were made. Video input
currently works through the ML1 local command; deployed MP4 upload still needs
the existing Android/backend owners' integration.
