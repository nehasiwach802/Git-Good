# Review of the 24 supplied circuit photographs

Reviewed: 2026-10-31. All 24 JPEGs in `ckt breadboard/` were opened and visually
inspected. They are 24 distinct files showing several views/states of three setup
families, not evidence of 24 independently wired circuits.

## Capture families

| Family | Files | Visible contents | Intended use |
|---|---|---|---|
| Single IC / red LED | 13 files, 8:23:35 through 8:23:41 PM | One DIP IC, red LED, jumper wires and supply clips; LED visibly illuminated in some views and not in others | First real annotation target, using the student's 7400 identity |
| Three ICs / green LEDs | 8 files, 8:23:42 through 8:23:45 PM | Three DIP packages, two green LEDs, dense red/black wires | Later occlusion/crossing challenge; exact chip identities and circuit function still unverified |
| Discrete components | 3 files, 8:24:30 through 8:24:31 PM | Axial resistor-like and diode-like components with blue/white leads; one overview includes a transformer | Separate component/endpoint examples; no circuit-function or live-apparatus inference |

These families are provisional grouping metadata. LED illumination alone does not
establish a logic value, supply state or correct wiring. Photos may include moved
input jumpers or other changes; identical netlists across views have not been
verified. Loose parts on the table are not components of the breadboard circuit.

## Selected views

### Single-IC circuit: start here

- **Primary grid/reference view:** `WhatsApp Image 2026-10-31 at 8.23.36 PM (1).jpeg`.
  The overhead-style view includes nearly the whole board and readable row numbers
  in several regions. Numbering runs in the opposite screen direction from some
  other views; assign IDs from the printed board rather than screen orientation.
- **IC/endpoint detail:** `WhatsApp Image 2026-10-31 at 8.23.38 PM (1).jpeg`.
  The non-illuminated LED view avoids the strong red glare and reveals several
  insertion points and the chip body more clearly.
- **Additional side evidence:** `WhatsApp Image 2026-10-31 at 8.23.36 PM (2).jpeg`
  and `WhatsApp Image 2026-10-31 at 8.23.41 PM.jpeg`.
  Useful for tracing leads that overlap in the primary image.

The chip's 7400 identity remains student-reported. A complete part marking,
orientation and every pin-to-hole assignment are not independently established
by this review. No final reference/student netlist has been produced.

### Three-IC circuit

- `WhatsApp Image 2026-10-31 at 8.23.44 PM.jpeg`: useful close view of the three
  packages and many terminal rows.
- `WhatsApp Image 2026-10-31 at 8.23.45 PM.jpeg`: useful overview from another angle.
- The 8:23:42/43 views provide complementary wire paths, but several terminal
  contacts remain occluded. Do not assume all three ICs are 7400s.

### Discrete-component circuit

- `WhatsApp Image 2026-10-31 at 8.24.31 PM.jpeg`: best local component/lead detail.
- `WhatsApp Image 2026-10-31 at 8.24.30 PM (1).jpeg`: wider board/grid context.
- The other 8:24:30 image is primarily equipment/setup context; the circuit is
  small in the frame, so it is less useful for endpoint labels.

## What these photos improve

The new views provide more readable row numbers, several less-obscured insertion
points, LED-off visual examples and complementary wire angles. They are sufficient
to begin a small real annotation set rather than collecting more random web images.
They do not automatically supply verified labels for hidden endpoints or rail
continuity. The terminal-only generated board profile must be extended before
rail-connected endpoints can be mapped correctly.

## Prepared local artifacts

- `outputs/real-photo-review/image-index.jsonl`: filename, SHA-256, dimensions,
  provisional capture family and unlabelled status for each image.
- `outputs/real-photo-review/summary.json`: counts and split-grouping status.
- `outputs/real-photo-review/single-ic.reference.annotations.json`: image-bound
  starting session for the selected primary photo, with U1 and D1 placeholders.
- `outputs/real-photo-review/single-ic.board.json`: provisional 63-row terminal
  profile, excluding rails.

Every connection in the starting session remains unknown and unconfirmed. The
session is preparation for annotation, not model extraction or ground truth.
Use the same provisional split group for related views until independent wiring
layouts are verified; do not put adjacent views into train and test separately.

To open the prepared session:

```powershell
python -m labvision annotate "ckt breadboard/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).jpeg" --board outputs/real-photo-review/single-ic.board.json --session outputs/real-photo-review/single-ic.reference.annotations.json
```
