# Qwen vision-language QLoRA feasibility pilot — 2026-11-01

## Model choice

The user proposed Llama-3.2-11B-Vision, Qwen2-VL-2B-Instruct and Qwen2.5-VL-3B.
These are multimodal instruction models; the earlier DINOv2 experiment was an
encoder with a new localization head. A VLM can instead be adapted to structured
text observations, provided suitable image/answer supervision exists.

| Candidate | Action and reasoning |
|---|---|
| Qwen2.5-VL-3B-Instruct | Actually downloaded and tested with local 4-bit QLoRA. Fits the 8 GB GPU under the bounded input configuration below. |
| Qwen2-VL-2B-Instruct | Lighter fallback; not downloaded or tested in this task. |
| Llama-3.2-11B-Vision-Instruct | Not tested. Its much larger weight footprint leaves less training headroom on this GPU; prefer a larger GPU for a practical experiment rather than assuming 8 GB is sufficient. Access also requires accepting the gated model's conditions. |

Primary references: [Qwen2.5 model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct),
[Qwen2 model card](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct),
[Meta model card/access](https://huggingface.co/meta-llama/Llama-3.2-11B-Vision-Instruct),
[bitsandbytes installation support](https://huggingface.co/docs/bitsandbytes/installation).
Qwen2.5's published capabilities include visual grounding and video input; the
local experiment below uses individual extracted frames, not video-native SFT.

## What actually ran

Final run: `outputs/qwen-vl-pilot-v3`.

- Official `Qwen/Qwen2.5-VL-3B-Instruct` weights stored locally under
  `outputs/pretrained/qwen25vl3b`.
- PyTorch 2.11.0+cu128, Transformers 5.17.0, bitsandbytes 0.50.2,
  PEFT 0.21.2, Accelerate 1.15.0 in the isolated training environment.
- NF4 double-quantized language weights, FP16 compute, frozen unquantized vision
  tower and tied output head. The code verifies that zero vision linear modules
  are 4-bit; excluding the output head avoids a tied-weight quantization failure.
- Rank 8, alpha 16, query/value LoRA on the language decoder: **1,843,200 trainable
  parameters**. No vision/base-language weights are trained.
- Batch size 1, gradient checkpointing, FP16 autocast and gradient scaling.
  Image budget: **100,352 pixels**, approximately 128 merged image tokens. This
  restrictive input resolution is a major limitation for small wire contacts.
- **32 optimizer updates**, using a shuffled subset of all nine AI-labeled real
  training frames plus 23 synthetic training images. This is a resource/training
  smoke pilot, not a full VLM training regime or a controlled comparison with the
  30-epoch YOLO and 10-epoch DINO runs.
- Output target: JSON approximate wire-end region centers normalized 0..1000,
  including loose ends. No hole IDs, wire pairing, inserted/loose class, component
  pin supervision, circuit diagnosis or temporal annotation was supplied.
- User/image-prefix tokens are explicitly masked out of the loss; only assistant
  targets and end tokens are supervised. The full/prefix token sequences must
  match exactly or training refuses the sample. Images are hash checked.

The corrected run exited **0**, completed in **187.51 seconds** including loading,
before/after generation and training, and peaked at **5,995,014,656 allocated CUDA
bytes (5.58 GiB)**. Reserved GPU memory and other applications are additional.
This demonstrates that this restricted 3B configuration works on the laptop; it
does not establish feasibility for larger images, multiple video frames or 11B.

## Before/after observations

Both phases received only the image and fixed instruction prompt. Reference
annotations were used for scoring afterward, never supplied to generation.
The four test seed frames contain 34 **unreviewed AI** region proposals and were
already visually inspected during earlier development. They are not a blind
human-annotated real-world benchmark.

| Bounded generation check | Base Qwen | After 32 updates |
|---|---:|---:|
| Valid expected JSON objects | 4/4 | 0/4 |
| Matched AI reference regions at IoU >= 0.5 | 0/34 | 0/34 |

The post-update output was repetitive/truncated under the 256-new-token limit
and rejected by the strict parser. Do not interpret this as Qwen having zero
real-world visual accuracy, or as evidence that proper QLoRA cannot help. The
run used few, weak labels, a short optimization schedule, a restrictive image
budget, a specific prompt/schema and a strict localization metric. No improvement
was demonstrated by this particular pilot. Keep YOLO as the working experimental
baseline; do not replace it with this adapter.

No invented confidence is emitted with points. Evaluation uses uniform matching
weights internally only. Unknown fields, Boolean/NaN coordinates and out-of-range
points are rejected. No output is confirmed or assigned a hole.

## Artifacts and reproduction

Experimental adapter directory: `outputs/qwen-vl-pilot-v3/adapter`.
`adapter_model.safetensors`: 7,393,888 bytes, SHA256
`98b99f8e426b24ae0ce05b0c3e0a1eaeb25c6e447b7a0a6a27f5225f37edb18c`.
All 144 saved tensors are LoRA tensors, finite, totaling 1,843,200 parameters;
LoRA B matrices are nonzero. Full base weights remain necessary for inference.
The poor-quality adapter is retained for reproducibility, not promoted for use.

```powershell
outputs/training-env/Scripts/python.exe -m pip install -r requirements-vlm.txt
outputs/training-env/Scripts/python.exe tools/qwen_vl_pilot.py --model outputs/pretrained/qwen25vl3b --dataset outputs/endpoint-dataset-v3 --out outputs/qwen-vl-next --steps 32 --allow-pseudo-labels
```

Use a new output directory. Original data and earlier experiment artifacts are
preserved. Raw generations and metrics are in `before-predictions.json`,
`after-predictions.json` and `report.json` beneath the run directory.

The first attempt (v1) failed because the tied output head was quantized. A
working intermediate run (v2) also unintentionally quantized the vision tower
because the exclusion needed its full module path. It completed but did not
improve output; v3 fixes the path and explicitly guards the intended configuration.
These are separate artifacts, not extra successful training epochs of v3.

## Next decision

The hardware feasibility question is answered for the restricted 3B run. Before
committing to a longer VLM run, correct the real seed labels and define the desired
structured observation target. Teaching complete circuit observations requires
more than the approximate endpoint labels currently available. Evaluate any longer
run on newly reviewed, independent layouts. If exact contacts remain the target,
local crops/higher pixel budgets are worth testing; their benefit is not proven here.

All **78 ML1 tests pass**, including assistant-only loss masking and strict VLM
coordinate parsing. Source compilation and diff checks pass. No README, Android,
backend, ML2, deployed routes or default extractor behavior were changed. No Llama
or Qwen2-VL-2B training result is claimed.
