# Automatic grid proposal for touch-based wire entry

ML1 opt-in prototype. No training or Gemini request required. Backend and Android
deployment are separate; the existing upload routes are unchanged.

## Calling it

Install the existing optional `requirements-video.txt` dependencies.

```python
from labvision.autocalibration import detect_grid, suggest_hole
proposal = detect_grid(selected_jpeg_bytes, central_grid_board)
suggestion = suggest_hole(proposal, central_grid_board, selected_image_sha256, [x, y])
```

Or call existing `process_video(..., auto_grid=True)`. This tries each sampled
frame, adds `grid_proposal` to frame metadata and selected `ml1`, and prefers the
sharpest frame with a supported proposal. Explicit selected_frame_id wins.
Default `auto_grid=False` preserves existing behavior. Failed fitting leaves the
manual fallback intact; it never replaces a candidate or marks its board reviewed.

Input must be a complete, standard central A-J grid, 10-70 rows, without rails or
custom geometry. Use the **actual** full board row count, e.g. `make_board(63)`;
do not apply the 30-row exercise profile to a 63-row video. Currently requires a
near-overhead portrait view, board long axis near vertical and all end rows in view.
Strong rotation/perspective, glare, dense occlusion and partial boards can fail.

## Response and touch coordinates

`ml1-grid-proposal-1` contains image SHA256, native decoded image_size,
board_fingerprint, status, reason, holes (provisional ID -> pixel center), quality,
and a projective calibration. Status is `not_found` or `needs_orientation_review`.
Video wrapper may instead return `unavailable` for an unsupported profile/error.

Android draws these centers on the selected frame. Invert the image rendering
transform (letterboxing, zoom and pan) before sending touch pixels. Reject taps in
letterbox margins. `suggest_hole` validates image/board binding and returns an
unconfirmed `provisional_hole`; ambiguous taps have alternatives and no selection.
Frame changes invalidate the proposal. Do not use video coordinates or reuse a
different frame's mapping.

## Labels and confirmation

Automatic geometry removes the four-anchor clicking step, but does **not** read
printed labels. IDs provisionally assume A-J left-to-right and rows increasing
top-to-bottom. On the supplied real board, the printed row directions on the two
halves appear different, so these IDs must not silently become physical labels.
Backend/Android must establish a verified board-specific label mapping (including
each strip's row direction) and obtain visual alignment approval before committing
hole IDs. A known, verified profile can reuse that label convention with a standard
capture orientation; the image-specific geometric fit must still be recomputed.

`label_mapping(board, left_top="A63", right_top="F1")` supports independent row
directions and reversed column order, including swapped halves. These arguments
describe the printed label at the top-left hole of each detected five-column strip;
the example is illustrative, not automatically verified from the video. Ask once
for these two labels or use a verified profile/capture convention. Pass the result
as `verified_label_map` to `suggest_hole` to get a physical `hole` instead of only
`provisional_hole`. Taps still remain `confirmed=false`. Backend must own/store
the verified mapping; never infer its verification merely from a client payload.

`labels_confirmed=false`, `reviewed=false`; calibration anchors/checks are empty.
Existing manual calibration verification is deliberately not bypassed. Automatic
fit residuals are not fabricated human check clicks. ML2 owns an explicit acceptance
operation and persistence/version guards; Android owns overlay/orientation approval
and wire-pair taps. Existing correct_endpoint handles committed physical labels.
Do not send provisional labels as confirmed corrections or auto-confirm a circuit.

## Algorithm and evidence

Compact dark blobs -> long column lines -> two five-column strips separated by
the center channel -> cross-column row extent -> RANSAC homography. Spatially
interleaved observations are withheld from fitting for a geometric residual check.
This is still the same image and inferred correspondence, not independently labeled
ground truth. Repeated grids/cropped or unexpected layouts can remain ambiguous.

Six existing frames from one real video were checked: F1 produced a proposal,
F2-F6 were rejected. F1 matched 94.3% of configured grid positions, with 151 held-out
observations and 90th-percentile residual 0.089 pitch. Visual inspection of the
saved overlay shows alignment on central holes. These numbers are **not** hole-ID
accuracy or evidence of broad generalization. Outer rails are not included.

Preview locally:

```powershell
python tools/check_auto_grid.py outputs/video-upload-callable-v1/F1.jpg --rows 63 --out outputs/my-grid-preview
```

Creates grid.json, board.json and overlay.png. Synthetic regression tests cover
known coordinates with occlusion, wrong row counts, blank inputs, ambiguous taps,
frame/profile binding and failure fallback; video tests cover selection behavior.
