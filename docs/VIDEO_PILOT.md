# ML1 video pilot — 2026-11-01

**Update:** the initial transfer-learning run is now complete. See
`reports/ENDPOINT_TRANSFER_LEARNING.md` for weights, evaluation and commands.
The model predicts unreviewed wire-end regions; exact hole assignment remains
unimplemented for this video path.

The user reports mentor guidance to support video input and try task-specific
fine-tuning, with approximately eight hours remaining when that plan was discussed.
That replaces the earlier recommendation to defer any training experiment.
It does not establish that video improves accuracy or that training is complete.

## Received data and inspection

- 16 local MP4 files in `ckt breadboard vidoes/`, all readable and source hashes unique.
- Approximately 304.5 seconds total; individual clips approximately 14–26 seconds.
- Source resolutions include 576x1024, 1024x576, 464x832 and 832x464.
- The overview shows different red-wire arrangements on a breadboard. Some wire
  ends are loose rather than inserted. No IC/LED circuit examples are visible in
  that overview; this is an endpoint-detection pilot, not full-circuit training data.
- The board changes orientation within some clips. Calibrate each selected view
  independently, or estimate and validate its transformation. Do not reuse one
  image homography unchanged across a moving video.
- All 96 selected frames lack **reviewed real ground truth**. Fifteen frames now
  have AI seed proposals; the final training run uses those, not the noisier
  heuristic pass on all 96 frames. Source uniqueness does not prove
  independence of layouts. Splits and assembly IDs remain unassigned pending
  layout review; all views of one wiring layout must stay together.

## Reproduce preprocessing

```powershell
python -m pip install -r requirements-video.txt
python tools/prepare_videos.py "ckt breadboard vidoes" --out outputs/video-pilot-v2
```

Use a new/empty output directory. The original files are read only. The command
samples at most 48 frames per video, selecting the sharpest within each of six
temporal bins. JPEG frames preserve decoded orientation and resolution. Each
clip gets a contact sheet; `overview.jpg` shows one representative per clip.
The manifest records original/video and frame hashes, frame indices, timestamps,
timestamp source, dimensions and heuristic scores. Decoder timestamps are used
when available; otherwise time is explicitly estimated from FPS. Whole-frame
sharpness is not a measure of visible holes, useful angle diversity or accuracy.

`outputs/video-pilot-v1` is the initial inspection run (FPS-estimated timestamps).
`outputs/video-pilot-v2` uses recorded decoder timestamps where available.

## Next work and evidence required

1. Choose representative frames and establish which clips share an unchanged
   wiring layout before defining training/validation/test groups.
2. Prepare endpoint annotation proposals and review actual insertion locations.
   Red insulation tips, metal leads, loose ends and occupied holes are different
   visual targets; do not silently turn a color-mask tip into a confirmed hole.
   Propagated or AI-generated labels retain their provenance and need review.
3. Fine-tune a small pretrained endpoint detector once usable supervision exists.
   Include synthetic data only as separately identified training data, and judge
   real performance on reviewed, held-out layouts. Synthetic success alone does
   not establish transfer to phone videos.
4. For video inference, align selected views to board coordinates and retain
   per-frame evidence. Hidden or conflicting endpoints remain unresolved. Do not
   merge wires solely because their projected paths cross.
5. Compare a single-frame baseline and multiple views on the same held-out clips:
   endpoint precision/recall, exact hole assignment, unresolved endpoints and
   latency. No improvement percentage is currently established.

## Team scope and current limits

This work adds local ML1 preprocessing, experimental detector training and video
region inference. A pretrained YOLO11n was fine-tuned for 30 epochs; AI proposals
remain explicitly unreviewed. No video connectivity fusion is implemented yet.
The existing image extraction and ML2
handoff remain in place. Android video capture/upload and backend video acceptance
remain their owners' work; the deployed multipart image endpoint has not been
changed or claimed to accept MP4. README is unchanged.

Validation: all 16 videos decoded into 96 frames with zero extraction errors.
All 71 ML1 tests pass, including split-leakage safeguards. CPU prediction covered
all 96 frames; direct MP4 selection plus inference also passed.
