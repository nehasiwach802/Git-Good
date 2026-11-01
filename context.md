# Project Context: AI Lab Mentor (HackCBS 9.0)

## ML1 callable video handoff (2026-11-01)

- User selected backend video processing, then clarified ML2 owns backend.
  Isolated outputs/backend-video-worktree created for read-only inspection;
  no backend code modified. All implementation is in ML1 checkout.
- Added labvision.video_upload.process_video(local_path, board, ...): bounded
  frame selection, normalized JPEG bytes/metadata, optional cached detector per
  frame and existing extract_upload result for the selected JPEG. Cloud extraction
  runs only on selected frame when enabled. No fusion, inferred pairing or review.
- Contract docs/VIDEO_PROCESSOR_HANDOFF.md: ml1-video-1 result includes ml1,
  selected_frame_id, frames (bytes plus hashes/timestamps/dimensions/proposals),
  video provenance. ML2 stores bytes separately and binds candidate to selected
  JPEG hash; routes/jobs/storage/Android rendering remain teammate-owned.
- Actual MP4 smoke with CPU YOLO returned six frames and selected F1 in
  outputs/video-upload-callable-v1. 100 tests pass, compilation/diff checks pass.
  Missing detector keeps frame processing; bad decode/limits raise CandidateError.
  No wall-clock decoder guarantee; backend worker owns hard execution deadlines.

## Backend-compatible detector delivery (2026-11-01)

- extract_upload now optionally runs cached trusted local YOLO weights via process
  LABVISION_ENDPOINT_WEIGHTS, returning additive endpoint_detection metadata.
  Candidate semantics unchanged: no invented pairing/holes/review; disabled by
  default, unavailable detector leaves manual/Gemini flow usable. Native pixels.
- Actual existing backend Integrations.extract method at local tracking branch
  adf5abd exercised against updated ML1 and real 7400 image: succeeded, one
  unconfirmed proposal. This is method-level compatibility, not HTTP/deployment
  or recognition-quality proof. Backend source already retains extra ML1 metadata.
- Added labvision/detection.py, requirements-detector.txt, five upload/detector
  tests and tools/check_backend_detector.py. Review UI importer accepts upload
  results as well as standalone predictions. Android box rendering still needs
  its owner; no backend/API replacement. Source and checkpoint release supported.
- See docs/UPLOAD_DETECTOR_INTEGRATION.md. Implemented source pushed to
  origin/Abhiram through 0467bc7; no live host configuration changed.
- Verification: 95 tests pass, compilation and diff checks pass. Release archive
  outputs/releases/gitgood-ml1-detector-integration-v2.zip includes explicit
  original endpoint checkpoint and optional runtime requirements.
- Release v2 SHA256: 9a638e12a545c86c0a75a5ea53ab39fd83f3bb6b0c199adec1d0ecec37cca076.
  Raw source videos remain untracked; local training outputs are not in Git.

## Multi-view experiment (2026-11-01)

- Implemented SIFT/RANSAC view mapping, intermediate-frame roundtrip optical-flow
  fallback and distinct-view endpoint consensus. Ran actual 15 reviewed clips.
- Final outputs/multiview-v3: 6 of 75 non-reference mappings accepted; only
  video-15 added evaluation views. Validation-selected threshold .25/support1.
- Same-method four-frame development F1 single .6024 vs fusion .5684; TP25->27,
  FP18->28, recall .625->.675. No established F1 gain; single view stays default.
  Metrics differ from older Ultralytics native-box F1; do not conflate methods.
- 90 tests pass incl synthetic translation/tracking/vote guards. Detailed report
  reports/MULTIVIEW_EXPERIMENT.md. All output proposals unconfirmed, hole=null;
  existing review importer can load exact-image fused predictions. No API change.

## Extended component capture (2026-11-01)

- ML1 now represents opamp functional terminals +,-,out,vcc,vee and diode
  anode/cathode in validation, annotation, vision vocabulary and upload fallback.
  This does not add trained recognition or infer physical package pin mapping.
- Candidates containing new parts use reviewed internal_v1 handoff, even when
  hole-only; older fixed-alias ml1_v0.1 is bypassed. Partial new-part handoff
  remains blocked. Properties are empty/unconfirmed; no opamp gain invented.
- 85 tests pass. Actual saved ML2 parser accepts both parts, preserving DIODE as
  unsupported. Simulation/deployment not verified. See docs/EXTENDED_COMPONENT_HANDOFF.md.

## Detector-to-review implementation (2026-11-01)

- Added labvision/detector_review.py and annotation UI controls to load exact-image
  YOLO predictions and explicitly assign proposals to selected endpoints. Import
  leaves wiring unchanged; assignment requires validated calibration, invalidates
  review/pairing, and retains vision source/unknown visibility/unconfirmed status.
- tools/prepare_video_review.py now connects actual MP4 frame selection, YOLO
  inference and saved review session; optional --open launches existing UI.
  Real video smoke completed six frames and six proposals in
  outputs/video-circuit-review-v1/review-session.json. Board/rails still require review.
- 83 tests pass; compile/diff checks pass. docs/DETECTOR_CIRCUIT_REVIEW.md documents
  usage. Existing backend upload, teammate code and default model unchanged.
- Still pending: backend-specific integration, opamp/diode representation support,
  physical complete-circuit rehearsal. This is a local ML1 bridge, not deployment.

## Accepted deadline plan (2026-11-01)

- User approved this plan and requested sharing it in Meko. Accepted scope is
  assisted circuit extraction with reviewed connections and measurement feedback.

- User reports 2–2.5 hours left and app/backend/Meko integration working.
  Reviewed accessible shared build records and local ML1 entry points; no live
  deployment revalidation during this planning task. Preserve existing team flow.
- Local extract_upload still Gemini/manual only; trained YOLO is standalone.
  PART_PINS/handoff lack op-amp and rectifier diode support. These are concrete
  local ML1 gaps; five-experiment reference research is not full runtime support.
- Accepted next 120 minutes: 15m inspect current backend adapter/schema, 40m
  connect region proposals to calibrated review without guessed wire pairing,
  25m add missing component representations only where existing ML2 accepts them,
  25m real image-to-reviewed-observation-to-existing-backend rehearsal, 15m freeze
  and package. Extra 30m for video keyframe bridge if existing transport permits.
- Pause further training. Prioritize one working complete demonstration,
  then expand within the five-experiment scope. Do not silently label missing
  component/analysis support as implemented. This is a plan, not executed changes.

## Five-experiment scope and readings research (2026-11-01)

- User explicitly restricted implementation scope to NOT using 7400 NAND,
  Ohm's law, RC low-pass filter, inverting op-amp and half-wave rectifier.
- Added docs/FIVE_EXPERIMENT_READINGS.md: primary sources, required measurements,
  formulas/applicability, uncertainty policy, calculated examples and conditional
  diagnostic checks. Wrong readings alone do not establish equipment failure.
- Reproducible calculated fixtures: examples/reference-readings/five-experiments.calculated.json;
  generator tools/generate_reading_examples.py. These are not measured readings,
  backend payloads or approved reference records. No production integration added.
- Checked rectifier constant-drop mean against independent midpoint integration;
  verified five records and RC cutoff magnitude; git diff --check passed.
- Existing ML2/backend owns diagnosis. DC/current/diode/transient capability and
  exact component models need checking there before claiming all five supported.
  Shared memories now describe API 1.1; earlier local stub notes are historical.

## Reviewed-label retraining (2026-11-01)

- User completed 15 seed reviews (148 endpoints; 11 frames edited); video-07
  stays excluded. Dataset outputs/endpoint-dataset-reviewed-v2 contains no
  unreviewed pseudo labels: real 9/2/4 and synthetic 152/26/22 train/val/test.
- Retrained YOLO11n from official pretrained weights for 30 epochs, 277.52s.
  Checkpoint outputs/endpoint-train-reviewed-v1/fit/weights/best.pt.
- Same corrected four-frame development evaluation: mAP50 old .5381/new .5465;
  recall old .550/new .475 at evaluator-selected operating points. Mixed result;
  no clear quality gain or default replacement. Layout independence unverified.
- Updated evaluation to separate reviewed regions from AI-label agreement.
  All 80 tests pass. Report: reports/REVIEWED_ENDPOINT_RETRAIN.md.

## Assisted review usability update (2026-11-01)

- Seed reviewer now saves corrections automatically on mouse release, deletion,
  navigation and close, with atomic file replacement and safe resume from output.
- Added Confirm & next / Enter, skip uncertain frame, and reviewed count. Reopens
  at the first unfinished non-excluded frame; verifies saved seed identities.
- Two persistence tests pass (resume preserves corrections/originals; mismatched
  seed output rejected). No reviewed seed output existed at task start.
- Launched reviewer using examples/video-seed-proposals.json, saving separately
  to outputs/reviewed-video-seeds.json. Labels need actual review before retraining;
  existing YOLO remains experimental and cannot infer complete connectivity.

## Qwen VLM pilot update (2026-11-01)

- User proposed Llama-3.2-11B-Vision, Qwen2-VL-2B and Qwen2.5-VL-3B.
  Actually tested Qwen2.5-VL-3B with NF4 QLoRA on the existing 8 GB GPU;
  the other two were not tested. No gated Llama credentials were requested.
- Corrected final run `outputs/qwen-vl-pilot-v3` completed/exited 0: 32 updates on
  nine AI seed frames plus 23 synthetic images; rank-8 decoder Q/V adapters,
  1,843,200 trainable parameters, vision and base decoder frozen. Vision linears
  explicitly checked unquantized; output head excluded to preserve tied weights.
- Max image budget 100,352 pixels (~128 image tokens), batch 1, checkpointing;
  peak allocated GPU tensors 5.58 GiB, total run 187.51 seconds. This proves only
  restricted local 3B training feasibility, not full-resolution/video/11B training.
- Four-frame unreviewed AI-label check: base 4/4 valid JSON, zero region matches;
  after 32 steps 0/4 valid JSON (repetitive/truncated at 256 tokens), zero matches.
  No real-world accuracy or model-family conclusion follows from this tiny pilot.
  Keep YOLO as working prototype; the Qwen adapter is experimental, not promoted.
- Adapter `outputs/qwen-vl-pilot-v3/adapter`; raw generations/report retained.
  Earlier v1 tied-head failure and v2 unintended vision quantization preserved.
- 78 tests pass, including answer-only token masking/strict coordinate parsing.
  No teammate-owned implementations, README, APIs or default extractor changed.
- Details/commands: `reports/QWEN_VLM_PILOT.md`. Next: review labels and define
  richer VLM targets before a longer run; current supervision teaches regions only.

## LoRA experiment update (2026-11-01)

- User requested a LoRA experiment on a larger vision model. Completed 10 epochs
  on pretrained DINOv2-base with rank-8 query/value adapters and a heatmap head.
  87,138,049 total parameters, 557,569 trainable; peak allocated CUDA tensors
  approximately 1.10 GiB, training loop 116.026 seconds.
- Adapter: `outputs/lora-dinov2-v1/best-adapter.pt`; requires the exact local
  DINOv2 base. Base hash and adapter key set are checked before inference.
- Same v3 synthetic/unreviewed AI-seed dataset as YOLO; no new human ground truth.
  Same-data region-center matching selected thresholds only on validation:
  synthetic F1 YOLO=0.980 vs LoRA=0.765; four-frame AI-label agreement F1
  YOLO=0.604 vs LoRA=0.387. These are not real detection/hole accuracy estimates.
- Keep YOLO as the working experimental baseline; this bounded LoRA run did not
  improve the preliminary score. Different input sizes/objectives limit attribution.
- Native MP4 LoRA CPU smoke and comparison both exited 0. All 74 ML1 tests pass.
  No teammate implementations, README or deployed APIs changed.
- Details and commands: `reports/LORA_VISION_EXPERIMENT.md`; preview:
  `outputs/lora-comparison-v1/comparison.jpg`.

## Video pilot update (2026-11-01)

- Transfer learning completed: pretrained YOLO11n, 30 epochs, 237.86 seconds on
  RTX 4060; checkpoint `outputs/endpoint-train-v1/fit/weights/best.pt`.
  Target is wire-end regions, not exact insertion points, hole IDs or connectivity.
- Final dataset v3 uses 138 assistant visual proposals from 15 seed frames
  (9 train / 2 validation / 4 test), plus 200 grouped synthetic images. One crowded
  seed is excluded. AI labels remain unreviewed and real groups provisional.
- Synthetic test mAP50=0.992; AI-label test agreement mAP50=0.558, not real accuracy.
  Real previews still show rail/text false positives and missed ends. No measured
  video-versus-image accuracy gain or multi-view connectivity fusion yet.
- CPU detector inference processed all 96 frames; native MP4 CLI smoke test passed.
  `tools/predict_video_ends.py` accepts a local video or prepared frame manifest.
  `tools/review_endpoint_seeds.py` supports explicit human review before retraining.
- 71 ML1 tests pass. Details: `reports/ENDPOINT_TRANSFER_LEARNING.md`.

- User reports mentor guidance: accept user videos and try task-specific fine-tuning;
  approximately 8 hours remained at the planning discussion. No accuracy gain is
  established. This updates the previous recommendation to defer all training.
- Received 16 MP4s under `ckt breadboard vidoes/`, about 304.5 seconds total.
  `tools/prepare_videos.py` selects six temporally spread, relatively sharp frames
  per clip, records hashes and frame metadata, and creates contact sheets.
- Initial run: 96 candidate frames, 16 unique source hashes, no decode errors.
  See `outputs/video-pilot-v1/overview.jpg`; decoder-timestamp run is v2.
- Visual overview: varied red-wire-only arrangements, including loose wire ends.
  Suitable for an endpoint pilot; no new IC/LED supervision. Labels are not yet
  reviewed; assembly IDs/splits remain unassigned to avoid leakage between views.
- Optional OpenCV dependency installed; isolated CUDA training environment is
  available under ignored outputs. Native video upload remains an
  Android/backend owner integration; existing teammate interfaces unchanged.
- Details/reproduction/next steps: `docs/VIDEO_PILOT.md`. README unchanged.

## Current ML1 integration status (2026-11-01)

- Read shared/promoted Meko records before cross-team changes; ordinary
  agent-scoped recall omitted existing teammate work during an earlier task.
- User confirms the backend is deployed. Verified live URL:
  https://git-good-1.onrender.com/; `/health` reports `mode=stub`. Its published
  contract is multipart POST `/api/sessions` with `experiment_id`, `description`,
  `image`. Preserve the existing backend and Android interfaces.
- ML2 already implements generalized 2.0 reasoning and `ml1_v0.1` / `internal_v1`
  adapters on `origin/tanu`. ML3's shared records describe its memory adapter
  and MCP transport. Those implementations remain teammate-owned.
- ML1: calibration/review/export works, one reviewed real netlist revision 45,
  matched saved session, 18 visible real-data labels; automatic extraction is
  experimental. Local development baseline matched 2/7 central wire ends; Gemini
  image requests timed out. Supply routing in the reviewed graph needs checking.
- ML1-only `extract_upload` accepts the existing backend's image bytes and returns
  an unreviewed candidate or explicit manual fallback. `reasoning_input` delegates
  v0.1 to ML2's existing adapter and exports reviewed v0.2 through `internal_v1`.
  Tested against actual ML2 code; unsupported LED is retained, not simulated away.
- Duplicate standalone API, database, Docker and Android client files created
  before checking teammate status were backed up under ignored outputs and removed.
  No replacement service is running. Original ML1 work and user labels are preserved.
- Latest checks: 67 ML1 tests pass; real v0.2 handoff passes ML2's parser. Backend
  currently exposes an upload smoke test with models marked `not_run`; integrating
  the ML1 library into that existing route is distinct from deploying a new backend.
- Authoritative ML1 integration details: `docs/TEAM_INTEGRATION.md`.

The original product plan follows; its unchecked implementation status is historical.

Team: 4 (1 Android dev, 3 ML). Status: idea selected for further work, pending validation. Alternative still on the table: the laptop repair-quote idea (see the last section).

---

## 1. Problem statement

**General form**

> Students in hands-on practicals often can't tell whether a failed experiment reflects a conceptual misunderstanding, a wiring/procedural slip, or a faulty instrument. The information that would resolve this (what was observed, what was already tried, what an instructor verified) is rarely recorded and doesn't carry over to the next attempt or the next student. The same equipment faults and misconceptions get rediscovered every semester.

**Demo wedge:** undergraduate electronics labs. We state the pattern generally but only claim it for electronics, because that's what we build and show.

**Why it matters**
- Three different causes (concept, wiring, apparatus) look identical to a student: "the output is wrong."
- Time is wasted, confidence drops, and learning gets shallower.
- Faulty equipment stays faulty because nobody records, aggregates or reports the evidence.

**What we have not proven (be honest in the pitch)**
- No primary evidence from our own campus yet. Collecting this is a to-do item.
- Impact ceiling: the problem is real but narrower and milder per person than most social-impact topics. Execution has to carry it.

**Pitch line**
> Not a chatbot that remembers. A lab system that works out whether it's you, your wiring, or the equipment, and makes sure the next student never hits the same broken probe.

---

## 2. What we are building

A lab mentor app (Android + backend) that diagnoses *why* an experiment isn't working and turns individual sessions into verified shared knowledge using Meko for memory.

### Core design principle
The LLM **explains**; deterministic components **decide**. An experiment is a data record, not hard-coded logic, so adding an experiment never needs new code.

### Experiment record (created by the instructor)
- `experiment_id`, title, learning objective
- Reference netlist
- Expected measurements at named nodes (with tolerances)
- Allowed component set
- Optional: known common misconceptions

### Student flow
1. Student opens an instructor-approved experiment (list or assignment link). App loads the reference by `experiment_id` and any approved notes for the selected `equipment_id`.
2. Student uploads a photo of the breadboard and describes the issue.
3. App recalls relevant history from Meko (this student's earlier attempts, equipment notes, instructor-verified knowledge).
4. Vision proposes a netlist **with per-connection uncertainty**.
5. Student confirms the unclear connections (fallback: tap-to-mark connections manually).
6. **Netlist diff** against the reference identifies wiring differences (deterministic graph comparison).
7. **SPICE simulation** of the confirmed circuit predicts what the student should measure.
8. Student enters actual measurements.
9. **Hypothesis ledger** updates probabilities across three causes: wiring error, conceptual error, apparatus fault.
10. Mentor asks the highest-information next check (evidence-linked, not generic advice) and explains the reasoning.
11. Session outcome is logged.

### Attribution logic (the novel part)
- Netlist differs from reference → **wiring error**
- Netlist correct, student's expectation or reasoning wrong → **conceptual error**
- Netlist correct, measurements still off → **suspect apparatus**

### Cross-student equipment inference
When *different* students running *different* experiments show the same anomaly on the same `equipment_id` (e.g. scope #3, CH2), the likelihood of an apparatus fault rises sharply, because equipment is the constant. The system flags it to the instructor/technician with the supporting sessions listed.

### Knowledge promotion and lifecycle
- Flagged patterns go to an instructor review queue.
- Instructor approves → becomes shared knowledge with provenance (who approved, which sessions) and an expiry tied to the equipment.
- Technician marks equipment repaired → warning retires.
- Next student sees the approved note on arrival, before spending time debugging.
- Student controls: can view, correct or forget their own personal context. Student-level memory, equipment-level notes and instructor-verified knowledge are shown as separate, labelled layers.

### Safety rules
- No guidance on mains voltage, large capacitors or live probing; the mentor refuses and points to the instructor.
- Prefer diagnostic questions ("what does the scope show at node X?") over prescriptions.
- Unverified student claims never enter shared knowledge without instructor approval.

---

## 3. Scope

**In scope (must work live)**
- Two experiments built from the same engine, e.g. RC low-pass filter and inverting op-amp
- Fixed component library (resistors, capacitors, op-amp, LED, wires) on a standard breadboard layout
- Netlist diff, SPICE prediction, hypothesis ledger, student confirmation step
- Instructor create-experiment form and approval queue
- Equipment-fault flag from seeded multi-student sessions
- Personal-context view / correct / forget

**Second experiment is added live in the demo** through the same form, as proof the system is general.

**Out of scope**
- Arbitrary circuits and components
- Other lab domains (state this as future work, don't claim it)
- Real usage data (use scripted, clearly labelled simulated sessions)

---

## 4. Demo script (target about 3 minutes)

1. Instructor creates the RC experiment (reference netlist, expected values).
2. Student A uploads a photo, confirms two unclear nets, enters measurements. System attributes the fault to apparatus and logs it.
3. Show seeded sessions from other students, on a different experiment, with the same anomaly on scope #3 CH2.
4. System flags the pattern; instructor approves it, with provenance shown.
5. Student B opens the experiment and is warned about scope #3 before starting. Compare with Student B's experience without the note.
6. Instructor creates the op-amp experiment live; the mentor works on it immediately.
7. Student corrects or forgets a piece of personal context.
8. Technician marks scope #3 repaired; the warning retires.

---

## 5. What needs to be done

### A. Before building (first priority)
- [ ] **Verify Meko:** read the API/docs, confirm what memory operations it supports (store, recall, forget, scoping per user/equipment/shared) and the judging rubric. The whole design depends on this; I have not verified it.
- [ ] **Collect 5 real incidents from our campus** (seniors, TAs, lab-mates): a fault that cost multiple students time, or a repeated misconception. If we can't find 5, the problem is smaller than assumed; reconsider.
- [ ] **Finish the repair-idea review analysis** (about 20-30 Google Maps reviews plus Reddit threads) so the two ideas are compared on evidence. Decide which one to build.
- [ ] Pick the two experiments and lock the component library.

### B. Build, by role
**Android dev**
- [ ] Experiment list / assignment-link entry
- [ ] Camera capture + session UI
- [ ] Tap-to-mark connection fallback
- [ ] Measurement entry
- [ ] Mentor chat view, with evidence links and a personal-context view/forget control

**ML person 1: Vision and netlist**
- [ ] Breadboard photo to candidate netlist with per-connection uncertainty
- [ ] Constrained to the fixed component set and layout
- [ ] Evaluate on a small set of our own labelled photos

**ML person 2: Reasoning core**
- [ ] Netlist graph diff against reference
- [ ] SPICE integration (e.g. ngspice) to produce predicted readings
- [ ] Hypothesis ledger (wiring / concept / apparatus) and next-check selection

**ML person 3: Memory and knowledge**
- [ ] Meko integration: recall before guidance, store session outcomes
- [ ] Cross-student equipment aggregation and flagging
- [ ] Promotion queue, provenance, expiry and retirement
- [ ] Mentor prompt layer (explains deterministic results, applies safety rules)

**Shared**
- [ ] Backend/API and instructor web view (create experiment, approval queue)
- [ ] Seed data: scripted sessions across both experiments, labelled as simulated

### C. Before submission
- [ ] End-to-end dry run of the demo script on a phone, with network failure fallback
- [ ] Fallback path if vision fails live (tap-to-mark)
- [ ] Slides: problem (with the campus incidents), approach, live demo, limits and next steps
- [ ] Rehearse judge Q&A (below)

---

## 6. Risks and judge Q&A

| Risk / question | Answer |
|---|---|
| Vision on breadboards is unreliable | Constrained library and layout, always confirm with the student, tap fallback |
| "Works on one circuit?" | Two experiments from one engine; second one added live |
| "Isn't this RAG plus memory?" | Attribution is deterministic (graph diff, SPICE, ledger); the LLM only explains. Plus cross-student equipment inference and knowledge lifecycle |
| "Is the data real?" | No. Seeded sessions, labelled simulated. Pilot is the next step |
| Memory poisoning | Nothing is shared without instructor approval; provenance on every item |
| Unsafe advice | Hard refusal rules for mains, large capacitors, live probing |
| "Impact is narrow" | Agree it starts with electronics; the pattern (concept vs procedure vs apparatus) holds across practicals, but we only claim what we built |

---

## 7. Alternative idea (decision pending)

**Laptop repair-quote clarity:** owners can't tell what evidence supports a quote or what they're authorising. Problem relevancy was rated roughly 8/10 against about 7/10 for the generalised lab problem, but validation is weaker (only secondary evidence) and the ML role is shakier. Choose based on which one our evidence supports better; if both pass, repair has more impact potential and lab has the cleaner build and demo.
