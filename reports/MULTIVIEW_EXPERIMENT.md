# Multi-view endpoint fusion experiment

2026-11-01. User requested actual use of video perspectives. Implemented and ran:

- SIFT feature matching and RANSAC homography from each selected frame to its
  reviewed representative. Reject insufficient matches, weak inlier agreement,
  narrow coverage, high reprojection error and implausible projected image.
- Fallback using intermediate original video frames: forward/backward optical
  flow, short homography steps and chained transforms. Reject after weak links.
- Map detector region centers to the reference view and cluster nearby centers,
  counting at most one vote per source view. No wire identity or hole assignment.
- Select detection threshold and minimum view support on the two real validation
  frames only. Evaluate the four existing reviewed development frames separately.

Code: labvision/multiview.py and tools/evaluate_multiview.py. Inputs are the
original YOLO pilot's saved predictions (confidence >=0.25), corrected user labels
and reviewed dataset split assignments. No new training or reference wiring used.
Reference image identity is selected using the labelled frame hash; inference
geometry does not use labelled endpoint coordinates. This is an evaluation tool;
it is not a general-purpose live backend video route.

Run:

```powershell
outputs/training-env/Scripts/python.exe tools/evaluate_multiview.py --predictions outputs/endpoint-predictions-v1/predictions.json --labels outputs/reviewed-video-seeds.json --dataset outputs/endpoint-dataset-reviewed-v2 --video-manifest outputs/video-pilot-v2/manifest.json --out outputs/new-multiview-run
```

Final experiment: outputs/multiview-v3. Threshold 0.25 and minimum support one
selected by validation for both single and multi-view. With a single-view
fallback, a minimum support of one permits new detections from other views.

| Four-frame development check | Single view | Multi-view |
| --- | ---: | ---: |
| TP | 25 | 27 |
| FP | 18 | 28 |
| FN | 15 | 13 |
| Precision | 0.5814 | 0.4909 |
| Recall | 0.6250 | 0.6750 |
| F1 | 0.6024 | 0.5684 |

These use common-size center-region boxes and a validation-selected threshold;
they differ from the earlier 0.567 F1 calculated from Ultralytics box metrics.
Only compare columns under the same method. Overall 6 of 75 non-reference view
mappings were accepted (2 direct, 4 chained), and extra evaluation mappings were
accepted only for video-15. Several frames use only the identity fallback.
Repeated texture, blur, viewpoint changes and non-planar wires limit registration.
Chained flow can drift or follow background motion even after local checks.

Outcome: recovered two additional true regions but ten additional false
positives. No demonstrated F1 improvement; preserve single view as the default.
No measured generalization claim: four frames are development-seen, physical
layout independence unverified, and variants were explored in this session.
An apparent v1 gain (0.639) arose from threshold selection when no extra test
views registered; it is not evidence of multi-view improvement. v2 likewise
added no evaluation mappings. Those output folders remain for audit.

predictions.json can be loaded in the existing circuit-review window for the
exact reference image. All proposals retain confirmed=false, reviewed=false,
hole=null and source-view IDs. No backend/default model changed.

Validation: 90 tests passed including known planar translation, chained synthetic
video motion, blank-view rejection, image bounds and distinct-view vote checks.
Dense optical flow, SIFT and actual-video evaluations completed locally.
