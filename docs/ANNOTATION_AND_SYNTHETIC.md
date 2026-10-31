# Calibration, manual annotations and synthetic endpoint data

This milestone implements a local desktop annotation tool and procedural data
generation. It does not include a trained detector or automatic wire tracing.

## Install and launch

Python's Tkinter provides the desktop UI; Pillow displays photographs and renders
synthetic images. The numerical calibration/compiler remains dependency-free.

```powershell
python -m pip install -r requirements-vision.txt
python -m labvision annotate "C:\path\to\breadboard.jpeg" --board outputs/7400-photo.board.json --assembly-id 7400-build-001 --candidate outputs/7400-photo.manual-template.json
```

Pillow is already available in the development environment. Supply a board JSON
that describes the actual board. If no starting candidate is available, omit
`--candidate` and add components/wires/ports in the UI.

An assembly ID groups captures of one physical wiring layout. Reuse it for camera
variations of the same build; assign a new ID after rewiring. This allows training
and evaluation splits to keep near-duplicate builds together.

## Calibrate the hole grid

1. Click **Pick 4 known hole centers**. Click each center and enter its actual
   hole ID, such as A1, J1, J30 and A30 if all are visible. Use widely separated
   points spanning the board plane; plastic corners are not hole centers.
2. The tool fits a perspective mapping and draws a green grid overlay.
3. Click **Check another known hole** twice using two distinct holes that were
   not anchors. Each check must be within 0.25 hole-pitch units of its expected
   location. A bad check requires correcting the ID or recalibrating.
4. Inspect the full overlay too. Two checks are a basic gate, not proof of perfect
   calibration. Check more points across the used circuit region when possible.

Conventional A–J profiles assume one unit per hole pitch and a three-unit E–F
center separation (the central channel). This is a provisional geometry model,
not a measured description of every breadboard. A board can define explicit
`hole_positions: {"A1": [0,0], ...}` in pitch units; every profile hole must have
a unique position. Nonstandard and power-rail holes require explicit coordinates
and verified connectivity groups. Generated profiles deliberately exclude rails.

The mapping is planar. Click where a lead enters the board, not the elevated wire
arch or IC body. For the supplied angled photo, unreadable hole labels and hidden
insertion points still require a better capture or verification on the physical
board; the application does not manufacture those facts.

## Annotate

For visible outer rail holes missing from the profile, click **Add outer rail hole**
then its center. This creates R1, R2, etc. without changing central-grid labels.
Select a wire endpoint and click the new hole to label it normally. Reuse a hole
already added rather than adding it twice. These names identify physical holes,
not positive/negative supplies. Rail continuity remains unverified: reviewed
netlist export is blocked until the actual connected groups (including breaks)
are established in the board profile and `unverified_rail_holes` is cleared.
Saving a session also offers a board JSON save dialog; save both and use this
updated board with `--board` when resuming. Existing open windows must be
restarted after this code update; save their progress first.

- Add a component and select each physical pin in the endpoint list. For a 7400,
  identify notch/pin-1 orientation and annotate all 14 pins.
- Add a wire; annotate both `W1.a` and `W1.b` for that SAME physical wire. A crossing
  does not imply a connection. Use separate IDs for separate wires.
- Add explicit input, output, VCC and GND ports when their roles are known. Ports
  are logical taps and may share a hole with a physical lead.
- Click the selected insertion point. A point close to a unique hole snaps to it;
  ambiguous points remain unknown. The initial radius is 0.35 pitch units and the
  nearest-vs-second-nearest distance margin is 0.2. These are heuristics requiring
  real-photo evaluation, not calibrated confidence probabilities.
- Use **Mark selected endpoint hidden** for occluded/unestablished endpoints.
  This preserves an unknown instead of guessing its connection.
- Wheel zooms; scrollbars pan. You can remove mistaken objects and edit passive
  component SI values. Save partial sessions at any time.

Any annotation edit invalidates whole-circuit review. Recalibration clears old
pixel-derived hole assignments; annotate them again against the new mapping.
Sessions bind to the exact source image SHA-256. Loading a session for another
image or changed board geometry is rejected. EXIF rotation is not applied; labels
use native file pixels. An imported candidate without an image hash is a template:
its old holes are cleared so synthetic/example wiring cannot label a new photo.

Resume a saved session:

```powershell
python -m labvision annotate "C:\path\to\breadboard.jpeg" --board outputs/7400-photo.board.json --session outputs/my.annotations.json
```

## Exports

- **Save annotation session:** editable image-bound progress, including unknowns.
- **Export unreviewed candidate:** existing candidate schema v0.1. Requires a
  validated calibration but can contain unresolved endpoints. It remains unreviewed.
- **Export reviewed training labels:** after both explicit acknowledgments,
  exports label format v0.1 with visible endpoint pixels, holes, wire identities
  and assembly ID. Partial labels remain possible: `visible=null` is unlabelled,
  `visible=false` is explicitly hidden. Imported model-only guesses are excluded.
- **Export reviewed netlist:** requires acknowledgments plus all existing
  candidate validation/review rules. Unknown/ambiguous endpoints block it.

Training-label review is not proof of circuit correctness. Real exports have no
segmentation masks, traced wire paths or complete latent ground-truth graph;
those fields are null, rather than pretending they were annotated.

## Generate data

```powershell
python -m labvision synthetic --count 200 --seed 42 --variants 2 --out outputs/synthetic-v2
```

Use a new/empty output directory; existing data is not overwritten. The first
generated batch is already in `outputs/synthetic-v1/`:

- 200 PNG images representing 100 underlying layouts, two appearances each.
- Actual split counts: 152 train / 26 validation / 22 test images.
- A board profile, per-image JSON labels and visible-instance PNG masks.
- `manifest.jsonl` and `summary.json`.

The generator places a 14-pin DIP and 2–8 wires at non-overlapping physical holes,
renders curved paths and varies colors, perspective, brightness, blur and optional
occluders. Some scenes use same-color wires. Layouts are randomly wired examples,
not validated NOT circuits. They carry actual generated connectivity groups, not
an expected experiment answer.

Label format v0.1 contains `image_type`, `assembly_id`, `split`, image size, exact
transformed hole centers, calibration anchors/checks, component pins, paired wire
endpoints, wire paths and `electrical_groups`. Masks use 0 for background/board,
1 for the IC, 2+ for wire instances, and 65535 for an occluder. Masks describe
topmost visible objects, not complete hidden wire silhouettes.

Synthetic endpoint `hole`/`xy` preserve latent scene truth even when hidden.
**Use `visible=true` and `observable_hole` when supervising observable insertion
points.** Do not train a model to confidently reveal endpoints behind an occluder.
Real labels cannot provide hidden ground truth and keep it null instead.

All appearance variants of an assembly stay in one deterministic split. Split
counts can vary with seed/count. This prevents layout duplication across splits,
but synthetic holdout accuracy still does not establish real-photo accuracy.

These are stylized 2D fixtures: raised cable parallax, realistic reflections,
multiple component classes and photorealistic lighting remain future work. No
model has been trained, and no endpoint detection accuracy is claimed.

## Verification

```powershell
python -m unittest discover -s tests -v
python tools/audit_synthetic.py outputs/synthetic-v1
```

Focused checks cover homography round trips, degenerate anchors, independent
holdouts, uncertain snapping, board/image mismatch, occupied-hole rejection,
recalibration invalidation, exact synthetic path endpoints, visibility, seed
reproducibility and assembly-group split isolation.

The first batch passed a full 200-scene consistency audit: 3,924 visible and 888
hidden component/wire endpoints. This checks generated labels against generated
geometry and instance masks; it is not a detector accuracy measurement.
