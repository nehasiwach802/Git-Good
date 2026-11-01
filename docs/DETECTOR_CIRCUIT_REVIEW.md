# Detector proposals in circuit review

Local ML1 integration, not a backend/API change. Existing image upload still
uses Gemini/manual fallback; this does not silently replace its result schema.

Run with the isolated training Python (OpenCV and Ultralytics required):

```powershell
outputs/training-env/Scripts/python.exe tools/prepare_video_review.py --video "path/to/clip.mp4" --board outputs/7400-photo.board.json --weights outputs/endpoint-train-v1/fit/weights/best.pt --out outputs/new-video-review --open
```

Use a new output directory and a board profile matching the actual board.
The example 63-row profile excludes power rails; add actual outer holes and
review rail continuity in the existing UI. No rail connectivity is inferred.
The original YOLO pilot remains the baseline because reviewed retraining was
not a clear upgrade. Either checkpoint can be supplied explicitly.

The command extracts six frames, detects regions, chooses maximum sampled
full-frame sharpness, and saves review-session.json with image/model provenance.
Sharpness is not a guarantee of board visibility; other frames are preserved.
No calibration is copied between views. No parts or wire pairings are invented.

In the existing annotation window:

1. Calibrate four known holes and validate with two separate check holes.
2. Add a wire. Select its a endpoint, choose 'Use proposal for selected endpoint',
   and enter a cyan proposal ID such as P1. Repeat for b using the other end of
   that same physical wire. Do not pair by proximity alone.
3. Inspect each proposed hole. Detector box centers are approximate: click the
   actual insertion point to correct them. Add missing ends manually; ignore
   false positive boxes. Loose ends can remain unresolved/external as appropriate.
4. Add components/ports, check rails, values and identities, then use the existing
   review and export controls. Model proposals do not grant confirmation.

For an existing session, 'Load detector predictions' accepts predictions.json
from predict_video_ends.py. Exactly one frame must match its image SHA256 and
dimensions; wrong-image reports and invalid boxes are rejected before mutation.
Import alone does not alter connectivity. Applying a proposal invalidates circuit
review and wire pairing. Region centers have unknown physical endpoint visibility.

Validation: 83 tests pass including image identity, atomic bad-input rejection,
validated-calibration gate and unconfirmed assignment. Actual video smoke produced
six predicted frames and a review session with six proposals in
outputs/video-circuit-review-v1. No correct-circuit/end-to-end backend claim yet.
