# Optional endpoint proposals in existing backend uploads

`labvision.upload.extract_upload` now supplies additive `endpoint_detection`
metadata. Existing candidate, board, image, netlist, mode and status semantics
are preserved. YOLO proposals never become wires, paired endpoints, calibrated
holes or reviewed connectivity automatically.

The actual backend `Integrations.extract` calls extract_upload and its workflow
preserves extra result metadata under `ml1`. Therefore this feature can be enabled
after installing this ML1 source and optional detector dependencies on that host,
without changing its image request route. This does not deploy it or add mobile
rendering: the Android owner must consume `ml1.endpoint_detection` to draw boxes.
The existing local review window can load either predictions.json or the full
upload-result JSON; image hash/dimensions must match the open image.

## Enable on the existing host

1. Install `requirements-detector.txt` into the existing backend environment with
   a matching Torch/Torchvision build for that platform. This detector was tested
   with Ultralytics 8.4.195 and the local isolated Torch 2.11 environment. CPU
   deployment has not been load-tested; confirm host memory/startup capacity.
2. Place the trusted packaged `models/endpoints.pt` on the host. Original YOLO
   pilot SHA256:
   `b2942301b590ca6bd8fd7a9d4214e34a51acb17630a866df02ac1581d007a191`.
3. Set process environment `LABVISION_ENDPOINT_WEIGHTS` to its absolute path.
   Set `YOLO_CONFIG_DIR` to a writable runtime directory if the host requires it.
   The existing Gemini .env loader intentionally reads Gemini settings only.
4. Restart through the team's existing deployment process. Verify an image
   upload returns `ml1.endpoint_detection.status=unreviewed_region_proposals`.
   When unset, detector status is disabled and no optional model imports occur.

Local inference is independent of the backend's Gemini vision-enabled flag.
If Gemini is disabled, mode remains manual even when endpoint boxes are returned.
That is intentional: approximate regions do not supply a complete candidate.
Model instances are cached per process and prediction is serialized by a lock.
The local inference stage has no hard wall-clock timeout; test resources on the
actual host. The existing timeout parameter still applies to Gemini extraction.

## Output shape

```json
{
  "mode": "manual",
  "status": "manual_entry_required",
  "endpoint_detection": {
    "status": "unreviewed_region_proposals",
    "model_sha256": "...",
    "target": "wire_end_region",
    "real_accuracy_established": false,
    "videos": [{"video_id": "uploaded-image", "frames": [{
      "sha256": "...", "image_size": [739, 1600],
      "proposals": [{"id": "P1", "box": [10, 20, 30, 40],
        "score": 0.8, "hole": null, "confirmed": false,
        "reviewed": false, "kind": "unknown", "source": "experimental_detector"}]
    }]}]
  }
}
```

`videos` is the existing prediction-report container used by the review importer;
this image result is a single-frame report, not evidence of a video upload route.
Coordinates use native decoded file pixels without EXIF rotation. Scores are
uncalibrated. Nothing in these boxes identifies wire pairing, diode polarity,
component identities, values or actual insertion holes. A UI may show the boxes
as editable hints, never as established connections.

Missing dependencies/weights or expected runtime detector errors yield only
`status=unavailable,error_code=endpoint_detector_unavailable`; no raw error
details or filesystem paths are exposed. Manual/Gemini processing can proceed.
Invalid images are rejected before either model is called.

## Actual verification

tools/check_backend_detector.py reads the actual extract method from the local
remote-tracking backend branch, and executes that method against current ML1.
This isolates extraction without starting auth, HTTP, persistence or product
memory. On the real 739x1600 reviewed 7400 photo it completed and returned one
unconfirmed proposal. That sparse result reinforces that recognition is limited
on complex circuits; successful transport is not successful full extraction.

Result: outputs/backend-detector-smoke-v1.json. The backend method uses exactly
the existing call signature; no backend files were modified. Current deployment
and phone rendering remain unverified by this local check.

For local video-to-review preparation use docs/DETECTOR_CIRCUIT_REVIEW.md. For
opamp/diode capture limits use docs/EXTENDED_COMPONENT_HANDOFF.md. Multi-view
fusion remains experimental and is not enabled by this upload feature.
