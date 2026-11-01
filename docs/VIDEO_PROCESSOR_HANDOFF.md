# ML1 callable video processor

Owner: ML person 1. Backend video ingestion, authentication, storage, job
scheduling/deadlines, routes and Android transport remain ML2/backend and Android
responsibilities. No backend implementation is supplied or replaced here.

## Call from the existing backend worker

```python
from labvision.video_upload import process_video

result = process_video(
    saved_video_path,
    experiment['board'],
    known_parts=experiment['reported_parts'],
    try_vision=settings.vision_enabled,
    timeout=20,
)

selected = next(f for f in result['frames']
                if f['id'] == result['selected_frame_id'])
selected_image_bytes = selected['jpeg_bytes']
ml1_result = result['ml1']
```

Requirements: `requirements-video.txt`; optional YOLO uses
`requirements-detector.txt`, its Torch/Torchvision environment and trusted local
weights. Process environment `LABVISION_ENDPOINT_WEIGHTS` enables the same cached
detector used by image uploads, or supply an `EndpointDetector` as `detector=`.
No detector configuration means valid frames and manual/Gemini ML1 still return.
Default `try_vision=False` makes no cloud request. With True, only the selected
image is sent to Gemini. The detector runs once per returned frame; the selected
image's detector report is reused in extract_upload, not recomputed.

The path must be a staged local file, not a URL. Backend owns the file lifetime
and deletes its original according to its retention policy. Temporary extracted
files are always removed by ML1; returned JPEG bytes remain usable after return.

This is synchronous preprocessing. Run it in a worker, not the async event loop.
If a hard decoder deadline is needed, the backend owner must execute the call
in a killable process; library limits are not a wall-clock execution guarantee.

## Return contract: `schema_version=ml1-video-1`

| Field | Meaning |
| --- | --- |
| `status` | `needs_circuit_review` |
| `selected_frame_id` | One of the returned frame IDs, e.g. F1 |
| `selection` | maximum_sampled_sharpness or explicit_frame_id |
| `video` | SHA256, byte count, metadata FPS/duration and frame count |
| `frames` | One to six frames by default; fewer if sampling cannot decode all bins |
| `ml1` | Existing extract_upload output for precisely the selected JPEG |
| `limitations` | Selection/geometry/review caveats |

Each frame contains `id`, `jpeg_bytes` (Python bytes), `sha256`, `size_bytes`,
`content_type=image/jpeg`, `width`, `height`, `decoded_size`, `frame_index`,
`timestamp_s`, `timestamp_source`, `sharpness`, and `endpoint_detection`.
The latter has the existing disabled/unavailable/proposal-report semantics.
IDs and timestamps identify frames within this result, not stable circuit objects.

**Do not JSON-serialize jpeg_bytes or put raw frames in the session snapshot.**
Persist the selected bytes as the session image and store alternate JPEGs through
existing backend storage. Publish only metadata and authenticated asset references
chosen by the backend owner. Never publish temporary local file paths.

The following identities must hold before storing a candidate:

```python
assert ml1_result['image']['sha256'] == selected['sha256']
assert ml1_result['candidate']['image_sha256'] == selected['sha256']
```

The candidate and endpoint coordinates refer to the normalized returned JPEG,
including its decoded orientation, not the original video resolution. No EXIF
transform is applied later. Frames preserve aspect ratio and are resized only
when necessary. Backend should use the returned image receipt; a video hash
must never replace a selected-image hash in candidate review.

If the student chooses an alternate frame, start a new image-bound extraction
and calibration/review on that JPEG. Never copy hole assignments or confirmation
from the old view. `selected_frame_id=` can select a known returned frame ID on
a repeat call with the same file/sampling configuration. IDs are reproducible
within that configuration, but persist the first result rather than relying on
repeat decoder behavior.

## Bounds and errors

Defaults: input <=50 MiB; reported duration <=60 seconds; decoded frames
<=8,500,000 pixels; six temporal bins from up to48 sampled frames; output JPEG
long edge <=1600; each output <=5 MiB. Metadata is checked before sampling and
actual decoded pixel size checked before processing. Duration is metadata-based.
The backend must enforce its own upload/container/MIME policy and request size
before invoking ML1; this library is not an HTTP video validator.

Invalid files, excessive bounds, failed decoding or unavailable explicit frame
IDs raise CandidateError. Missing OpenCV is a dependency/configuration error.
Expected detector errors yield unavailable proposal metadata and keep frames;
Gemini failures use the existing manual_fallback candidate. No reference wiring,
truth table or expected readings are inputs. Reported component identities and
physical board geometry remain allowed inputs.

No components/wire pairs/holes are inferred by video preprocessing. Candidate
review remains required; multi-view fusion is not enabled. Maximum whole-frame
sharpness is a heuristic and can favor the background over the breadboard.

## Verification and reproduction

100 tests passed. New tests verify byte/hash/dimension binding, temporary-file
cleanup safety, explicit frame selection, detector/provider call counts, invalid
file/size/duration/pixel rejection and detector-failure fallback.

Actual user MP4 processed with the original trained YOLO on CPU, returning six
frames, selected F1, unreviewed detector reports and a manual-entry candidate.
Artifacts: outputs/video-upload-callable-v1/result.json and F1.jpg through F6.jpg.
This is real local preprocessing, not a live upload/deployment verification.

```powershell
outputs/training-env/Scripts/python.exe tools/check_video_upload.py --video "clip.mp4" --board outputs/7400-photo.board.json --weights outputs/endpoint-train-v1/fit/weights/best.pt --out outputs/new-callable-smoke
```

The smoke tool writes frame bytes separately and serializes metadata to JSON,
illustrating how the backend should separate assets from session metadata.
