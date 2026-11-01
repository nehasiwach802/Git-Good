# ML1 video handoff review and ML2 work — 2026-11-01

Reviewed origin/Abhiram393732a after refreshing remote refs. Current branch tanu.
Backend planning notes preserved in git stash before switching. No runtime edits
or model/provider calls were made for this review. This supersedes an incomplete
image-only assessment; video preprocessing is delivered source, not merely a plan.

## Actual ML1 changes

- f14e04d: optional cached YOLO endpoint proposals integrated into extract_upload;
  proposals stay unreviewed boxes with no automatic holes/wire pairs.
- Extended opamp/diode representation across capture/validation/vision/fallback:
  opamp functional pins +,-,out,vcc,vee and diode anode,cathode. No guessed gain,
  physical package mapping or diode model. reasoning_input routes these and0.2
  through reviewed internal_v1, not fixed-alias ml1_v0.1.
- 393732a: labvision.video_upload.process_video(local_path,board,...) calls bounded
  extraction, selects one frame by sampled whole-frame sharpness or explicit ID,
  runs optional detector per frame, reuses selected detection for extract_upload,
  and returns selected-image candidate plus all extracted JPEG bytes/metadata.
- Default limits50MiB,60metadata seconds,8.5MP decoded input,6frames/48samples,
  outputlongedge1600,eachJPEG<=5MiB. These are not a hard wall-clock deadline.
- schema ml1-video-1: video metadata,selected_frame_id,frames,ml1,limitations.
  Candidate/image hashes refer to normalized selected JPEG,never original video.
  Sharpness may favor background. No automatic calibration transfer,pairing,
  multiview fusion or review approval. Experimental multiview code is separate.
- ML1 reports100tests and a localMP4CPU run returning6frames/manual candidate.
  Source review confirms implementation; this task did not rerun that video.
- Training comparison reports mixed results: reviewedretrainmAP50.5465 vs.5381,
  recall.4750 vs.5500 on a development set. No universal accuracy improvement or
  production/default checkpoint replacement. Weights/deployment remain explicit.

## ML2 changes on tanu (shared reasoning layer)

1. Integrate reviewed ML1 handoff compatibility while preserving ML2 bounds and
   strict revisions. Use ML1 reasoning_input rather than hardcoding hole-only
   aliases. New extended parts stay reviewed-only; unknown evidence stays unknown.
2. Add/test a small selected-frame normalization boundary that validates schema,
   selectedframeexistence,receipt/candidate/JPEGhash and dimensions,outputs owned
   image bytes plus existing candidate/board and metadatawithout bytes orpaths.
   Reasoning must not consume rawMP4 or pool boxes from different frames.
3. Bind capture identity to selected JPEG and frame/source provenance; selecting
   another frame resets calibration,review,diagnosis and stale revision references.
   Test selectedframehash mismatch and replay/staleframe protection.
4. Preserve OPAMP as unknown-properties until explicit idealmodelgain configuration;
   DIODE remains unsupported electrical behavior until an actual model/analysis
   exists. OhmDC/rectifiertransient are not enabled merely by detector support.
5. Tests: normalized video selected observation through actual ML1handoff andML2;
   unknown endpoint,corrected wiring,externalterminals,OPAMPmissinggain,DIODEgap,
   framechange and candidatehash mismatch. Keep 1.0/2.0 compatibility.

## ML2/backend changes on backend/android-connection-test

The existing backend already calls labvision.handoff.reasoning_input. Preserve it.
It currently only accepts/persists images and calls extract_upload, not process_video.

1. Vendor latest reviewed ML1runtime,installOpenCVheadless+NumPy video deps; opt-in
   detector additionally needs matchingTorch/Torchvision/Ultralytics and trusted
   weights. Do not automatically replace checkpoint or download arbitrary weights.
2. Add an additive authenticated separate video upload (proposed path
   POST /api/v1/sessions/{id}/video; not yet finalized withAndroid),keepingJSON
   session creation andexisting image route/events. Idempotency,ownership,version
   checks andmedia-typecapability metadata required. Streaming/spooling andbounds
   must be route-specific; current image6MiB/JSON512KiB caps cannot accept50MiB video.
3. Stage local video on persistent storage,enqueue worker job,call process_video
   outside eventloop/DBtransaction. Use killable process and configureddeadline
   for decoder/detector work; original library timeout is Gemini-only.
4. Persist framebytes as authenticated assets;selectedJPEG becomes sessionimage.
   Snapshot contains video/frame metadata andassetURLs only,no JPEGbytes orpaths.
   Validate selected JPEG/candidate hashes anddimensions before committing result.
5. Add frame selection event (proposed select_frame) and new image-bound extraction;
   clear old review/calibration/diagnosis and guard candidate/session versions.
   Persist first preprocessing result instead of re-decoding to recover frameIDs.
6. Keep detector unavailable/manual fallback honest; reject malformed/oversized
   video andensure deadlines/crash/restart/tempcleanup behavior;retention applies
   originalvideo,alternateframes and selectedimage,not just existingimageblob.
7. Update generatedOpenAPI,operatorflags/dependencies andAndroidcontract together.
   Current1.1 JSONcreation,nestedevents,expected_session_version andclose_session
   stay intact. New route/frameevent needAndroidagreement before claiming final.

## Android/ML3 boundary

Android adds video picker/upload,processing state,frame thumbnails/selection and
proposal overlay/correction on selected JPEG. It must not rotate or rescale boxes
without mapping decoded image coordinates. ML3 continues consuming actual ML2
results; no rawvideo reasoning or automatic confidence/probability invention.

## Implementation order

First selectedframe->existingreviewedML2 compatibility on tanu; then propagate
shared code into backendbranch and add bounded authenticatedvideo flow; then
Android frameUI and one actualvideo end-to-end test. Do not re-train or redesign
reasoning to consume rawvideos. No all-five-experiment or deployed-video claim.

Source references: ML1 docs/VIDEO_PROCESSOR_HANDOFF.md,
docs/UPLOAD_DETECTOR_INTEGRATION.md,docs/EXTENDED_COMPONENT_HANDOFF.md,
reports/REVIEWED_ENDPOINT_RETRAIN.md; existing backend integrations/workflow.
