# ML1 next move: geometry, synthetic labels and a small real-photo benchmark

Research date: 2026-10-31. Proposal by the coding assistant supporting ML person 1;
this is not a new team-wide scope decision. No training or dataset download was
performed in this research pass.

Implementation update: the proposed local calibration/annotation tool and
procedural generator are now implemented. See `docs/ANNOTATION_AND_SYNTHETIC.md`.
The first batch contains 200 stylized scenes across 100 layouts and passes a label
consistency audit. Model training and held-out real-photo evaluation remain pending.

## Recommendation

Build a calibrated endpoint-to-hole pipeline. Use procedural synthetic scenes for
known geometry and wire pairing, plus a small independently labelled real-photo
benchmark. Delay model training until that benchmark shows which visual subtask
needs improvement. The existing connectivity compiler remains useful unchanged.

The earlier blanket recommendation to defer fine-tuning needs this qualification:
we can generate training labels ourselves for a narrow task. Synthetic data is
worth investigating now; a full photo-to-netlist model is still too broad for the
current demo. A server timeout/503 is not a visual accuracy measurement.

## What has to be recognized

1. Board coordinate system: which image locations correspond to actual hole IDs.
2. Component identity, orientation and terminal positions. User-confirmed IC
   identity plus a verified pinout can reduce the recognition task.
3. Each wire's two insertion points and their shared wire identity.
4. Visibility/uncertainty: a hidden insertion point is not a reliable prediction.
5. Internal board connectivity from a verified profile, including split rails.

Endpoints alone do not resolve connectivity if we cannot determine which two
belong to the same wire. Same-color wires and crossings make that pairing harder.
Likewise, a component bounding box does not locate each individual lead.

## Which data sources actually help

| Source type | Useful supervision | What still needs work |
|---|---|---|
| Photo plus schematic | Intended circuit/reference graph; component vocabulary | Actual pixel/terminal/hole annotations; confirmation that the photographed build matches the schematic |
| Annotated component photographs | Component classes and bounding boxes/masks | Pin positions, insertion holes, endpoint pairing and visibility |
| Editable breadboard diagram with explicit wiring | Known layout and graph for a rendered example | Exact rendered pin/hole coordinates and transfer to real photographs |
| Procedural 2D/3D scene | Automatically known endpoints, paths, holes, identities and visibility | Realistic appearance and independent real-image evaluation |
| Small manually labelled real set | Direct measurement of the actual task | Some manual work, but initially dozens of endpoints can be enough to expose failures |

A schematic is not automatically a label for the real photograph. We must preserve
accidental wrong wiring; copying the intended diagram would teach the model to
erase the errors the project is supposed to diagnose.

## Useful resources found

- [Princeton VLM Tunnel dataset card](https://huggingface.co/datasets/princeton-vl/vlmtunnel/blob/main/README.md)
  and [generator code](https://github.com/princeton-vl/vlmtunnel): includes synthetic
  circuit wire-tracing tasks with destination-answer labels. Useful for testing
  wire-pairing reasoning and generating crossing/color variations. It is not a
  ready-made real breadboard pin-to-hole dataset. Inspect/adapt the generator to
  retain endpoint coordinates if needed. Dataset card lists MIT; code repository
  lists BSD-3-Clause.
- [Full Cable + Synthetic](https://universe.roboflow.com/fa23ai02-objdetection-2/full-cable-synthetic):
  public object-detection dataset including Wire, Breadboard, Resistor and LED.
  Listed license CC BY 4.0. Potential component/wire localization bootstrap;
  the inspected page does not establish paired endpoints or hole-coordinate labels.
- [Timothy Evans's breadboard synthetic-data account](https://roboflow.com/blog/synthetic-data-breadboards):
  reports combining 500 Unity-generated examples with roughly 250 real labelled
  images for resistor/wire component detection. This supports the feasibility of
  synthetic generation, not guaranteed circuit-connectivity accuracy. A full Unity
  environment would add setup work for this deadline.
- [Wokwi diagram format](https://docs.wokwi.com/diagram-format): stores part
  positions and connections. Potential source for paired rendered diagrams and
  graphs; not every diagram explicitly gives breadboard insertion holes, and
  rendered coordinates still need derivation. We have not built or validated an
  importer. No assumption of 7400 simulation support is made.
- [Breadboard-Vision](https://github.com/Fontaine-bleau/Breadboard-Vision): an
  experimental implementation advertising grid fitting, short-wire tracing and
  optional learned detection. Its README explicitly says the public repository
  excludes training photos, annotations and weights. Candidate algorithm reference,
  not a supplied trained solution; no code or performance was independently tested.

Random images can become a dataset after we annotate the exact task. Prefer sources
with editable geometry or known labels to reduce manual work. Record source,
permitted use, label coverage and image type in the manifest. Do not mix screenshots
and photographs into one accuracy claim.

## Concrete implementation order

### First: calibration and manual endpoint baseline

Use one board profile and top-down captures. Select four known, well-spaced hole
centers with their actual hole IDs, fit a perspective mapping, and validate it on
additional visible holes. Full-board plastic corners alone do not establish hole
pitch or origin unless the profile includes those measured offsets.

Draw the predicted hole grid over the image. Start with endpoint clicks or model
proposals in image coordinates, map them into the board frame and snap to the
nearest legal hole only when residual distance/margin allow a clear assignment.
Map uncertainty to nearby hole alternatives rather than silently forcing a choice.
For example, a projected point between adjacent rows should request confirmation.

Calibration is planar: elevated wire arches and chip bodies are not hole centers.
Locate the insertion/contact point. Verify notch/pin-1 orientation separately.
Four points under a flat-board assumption cannot recover hidden connections.

This baseline requires no training set and will expose board/profile errors before
we spend time training a detector. It is also the Android manual fallback.

### Second: small real-photo benchmark

Proposed initial target, not a minimum-data guarantee: 10–20 clear photographs
covering several independently rewired layouts. Start with 1–3 visible wires, then
add crossings, same-color wires and the 7400. The circuits need not all implement
different experiments; varied physical layouts matter for this visual task.

Label actual visible wire endpoints, wire identities, hole IDs, component pins and
occlusion. A short video of one unchanged build gives camera variations, not many
independent assemblies. If using online photos, annotate only visible evidence and
keep hidden points unknown; diagrams can help cross-check but must not overwrite
the photographed circuit.

Reserve entire builds/layouts for evaluation before generating augmentations.
Keep crops, neighboring video frames and synthetic variants of one layout in the
same split. Include at least one wrong-connection example to catch reference leakage.

### Third: procedural synthetic generation

Start with a simple 2D renderer or compositor, not a generative-image model:

1. Sample a legal board layout and physical component/pin locations.
2. Sample wire endpoint pairs on free holes, including some deliberate miswirings.
3. Render wire paths with instance IDs and correct endpoints.
4. Save the image, endpoint coordinates, hole IDs, instance masks/paths and actual
   electrical graph from the same source scene.
5. Vary perspective, color, wire width/curvature, background, shadows, blur and
   occlusion. Apply geometric transforms to labels as well as images.
6. Preserve a visibility flag; latent coordinates behind an occluder are not visible
   evidence and must not be scored as confidently observable endpoints.

Proposed first batch: 200–500 generated scenes to validate labeling/training
plumbing. This is an engineering starting point, not evidence that the count will
train a useful detector. Start by inspecting ~20 examples. A real board background
with rendered wires can reduce appearance mismatch, but raster drawings will still
miss raised cables, lead reflections and realistic occlusion.

A photorealistic 3D renderer can come later. An AI-generated attractive breadboard
image does not guarantee correct physical wiring or exact annotations; use a
known-geometry generator when creating ground truth.

### Fourth: train only the demonstrated weak stage

If calibration is good but endpoint proposals are poor, train a small pretrained
keypoint/segmentation detector on the synthetic data and manually annotated real
examples. Keep wire pairing separate from endpoint localization so their failures
can be measured independently. Do not claim an ordinary wire bounding-box detector
solves either stage.

Start from a baseline that uses board geometry and simple visual processing; train
only when data, hardware and remaining time support the experiment. A small endpoint
detector is a more focused training target than a large multimodal model that emits
the entire netlist.

## Label requirements for the next module

An image record should include:

- Image/source ID, real/synthetic type, assembly/layout ID and split.
- Image size and verified board profile.
- Calibration correspondences: image `(x,y)` plus actual hole ID.
- Per wire: instance ID; each endpoint's pixel location, hole ID and visibility;
  optional visible path/mask; pairing certainty.
- Per component: class/part identity, orientation, visible terminal positions,
  holes, and identity/label provenance.
- Actual observed connections separate from intended reference connections.

This is an annotation plan, not a finalized team schema. Hidden endpoint pixels or
holes can be null. Do not synthesize human confirmation flags during import.

## Evidence needed to proceed

Track endpoint hole accuracy and coverage, wrong-wire pairing rate, false confident
assignments, correction count and final graph accuracy. Measure these on held-out
real builds, not just transformed synthetic scenes. If synthetic scores are high
and real scores are poor, treat that as a domain-transfer failure and adjust
capture conditions/rendering or add real annotations.

**Next implementation task:** a four-point calibration and endpoint-annotation
tool connected to the existing candidate/netlist compiler, followed by a small
procedural scene generator. This makes the fallback usable immediately and creates
the exact labels a later detector needs.
