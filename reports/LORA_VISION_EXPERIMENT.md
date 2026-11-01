# DINOv2-base LoRA pilot — 2026-11-01

## Outcome

Completed a local LoRA experiment on **facebook/dinov2-base**, a pretrained
vision-transformer feature encoder ([model documentation](https://huggingface.co/docs/transformers/model_doc/dinov2)).
The base weights stay frozen. Rank-8, alpha-16 low-rank adapters are injected into
the query and value projections of all 12 attention blocks. A new convolutional
heatmap head learns approximate wire-end centers. This implements the frozen-base
plus low-rank-update method described in the [LoRA documentation](https://huggingface.co/docs/peft/developer_guides/lora),
directly in PyTorch; PEFT is not a runtime dependency.

The bounded 10-epoch run completed in 116.026 seconds after initialization and
dataset caching on the RTX 4060 Laptop GPU. Total parameters: **87,138,049**.
Trainable: **557,569 (0.64%)**, comprising 294,912 LoRA parameters and 262,657 head
parameters. Peak allocated CUDA tensor memory was 1,185,102,336 bytes, approximately
1.10 GiB; this excludes reserved allocator memory and other applications.

Adapter checkpoint: `outputs/lora-dinov2-v1/best-adapter.pt`, 2,250,033 bytes.
SHA256: `460014ad98770145a08a0d58c3cb5292e784d7703c15cf0bdccbfcf1f1c69876`.
Frozen pretrained safetensors SHA256:
`d73036b56966966d07975d696bde331762f37297e2f095de8cea0040c3aa0841`.
Inference still needs the full pretrained backbone; the small adapter does not
make the foundation model itself smaller. Loading verifies base-model identity
and checks that the adapter contains exactly the expected trainable parameters.

## Data, target and evaluation limits

Used the same v3 dataset as the YOLO pilot: 152/26/22 synthetic train/validation/test
images plus 9/2/4 real seed frames with unreviewed assistant region proposals.
No new human ground truth was created or claimed. Split groups remain provisional
for real videos and all real representatives were seen during development.

Target remains **wire-end regions**, including loose ends. It does not classify
inserted versus loose ends, assign exact holes, pair wires, identify ICs, compile
netlists or fuse calibrated views. Predicted scores are uncalibrated, and all
outputs retain `confirmed=false`, `reviewed=false`, `hole=null`.

DINO uses an aspect-preserving 448-square letterbox, the pretrained processor's
ImageNet normalization and a learned upsampling head. YOLO uses size 768 and a
different objective and augmentation pipeline. This is an exploratory comparison,
not a controlled architecture-only ablation or a claim that LoRA cannot work.

## Comparison

Both models' center proposals were converted to the same image-size-derived
regions, then matched one-to-one with IoU >= 0.5. Confidence thresholds were
chosen independently using mixed **validation** F1, not test labels: 0.8 for
DINOv2-LoRA and 0.5 for YOLO. These F1 scores are distinct from the earlier YOLO
mAP figures and should not be compared numerically with them.

| Model | Synthetic test F1 (22 images) | AI-label agreement F1 (4 images) |
|---|---:|---:|
| YOLO11n transfer-learning pilot | 0.980 | 0.604 |
| DINOv2-base LoRA, 10 epochs | 0.765 | 0.387 |

On the four AI-labeled frames, YOLO matched 16 of 34 proposed regions with 3 extra
regions; LoRA matched 12 with 16 extras. These counts measure agreement with
unreviewed labels, not established real detection accuracy or exact-hole accuracy.
No video-versus-image gain has been measured. Keep YOLO as the working experimental
baseline; this run provides no evidence to replace it with LoRA.

Artifacts:

- `outputs/lora-dinov2-v1/training-report.json`: epoch losses, parameter counts,
  validation threshold selection, separate synthetic/pseudo-label metrics.
- `outputs/lora-comparison-v1/comparison.json` and `comparison.jpg`: same-data
  comparison and side-by-side real previews.
- `outputs/lora-video-smoke-v1`: successful direct-MP4 CPU inference on six views;
  prediction/rendering time 20.031 seconds, excluding decoding and model loading.
  That is a local smoke timing, not a controlled latency benchmark.

## Reproduce with existing artifacts

Use the existing CUDA environment. DINOv2 weights are public and were downloaded
to `outputs/pretrained/dinov2-base`; only config, processor config and safetensors
are needed. All subsequent training/inference uses local weights.

```powershell
outputs/training-env/Scripts/python.exe -m pip install -r requirements-lora.txt
outputs/training-env/Scripts/python.exe tools/train_lora_endpoints.py --dataset outputs/endpoint-dataset-v3 --pretrained outputs/pretrained/dinov2-base --out outputs/lora-dinov2-next --epochs 10 --batch 2 --allow-pseudo-labels
outputs/training-env/Scripts/python.exe tools/compare_lora_endpoints.py --dataset outputs/endpoint-dataset-v3 --pretrained outputs/pretrained/dinov2-base --adapter outputs/lora-dinov2-v1/best-adapter.pt --yolo outputs/endpoint-train-v1/fit/weights/best.pt --out outputs/lora-comparison-next
outputs/training-env/Scripts/python.exe tools/predict_lora_video.py --video "path/to/video.mp4" --pretrained outputs/pretrained/dinov2-base --adapter outputs/lora-dinov2-v1/best-adapter.pt --out outputs/lora-video-next --device cpu
```

Use new output directories. The adapter loader uses `weights_only=True` and
requires the exact base-weight hash. Training refuses pseudo-label data unless
the experimental flag is supplied. No pretrained fallback to random weights or
automatic download is performed by the training/inference code.

## Validation and next step

All 74 ML1 tests pass, including adapter initialization equivalence, frozen-weight
gradient protection and one-to-one matching safeguards. The comparison and native
MP4 smoke subprocesses exited 0. The training shell wrapper reported exit 1 after
PowerShell serialized Hugging Face progress output on stderr, although the Python
run wrote a complete 10-epoch report and loadable checkpoint. Subprocess-based
logging was used for the comparison/smoke checks to verify their actual exits.

Correcting seed annotations and obtaining new reviewed held-out layouts remain
more useful immediate steps than assuming a larger model will improve results.
Higher-resolution/local-crop experiments could address a possible localization
limit, but this run does not isolate that cause from supervision or optimization.
No backend, Android, ML2, deployed API or README changes were made.
