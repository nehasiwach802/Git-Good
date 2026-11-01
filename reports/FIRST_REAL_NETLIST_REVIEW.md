# First reviewed real-photo netlist

The user exported `examples/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).netlist.json` as schema 0.2, revision 45,
with status `reviewed_connectivity`. It contains 2 components (one reported 7400
and one LED), 8 jumper wires, 2 supply ports, 12 electrical nodes and 34
confirmed endpoint provenance records. Node references, endpoint-to-node
provenance and all wire merges pass consistency checks.

## Recorded supply routing needs checking

| Terminal | Recorded node | Expected relationship for the 14-pin 7400 |
|---|---|---|
| U1.14 | N0 | Same node as VCC (N4) |
| U1.7 | N4 | Same node as ground (N11) |

In the exported graph, pin 7 shares VCC's node and pin 14 does not reach VCC.
This is an inconsistency with the labelled supply roles and assumed 14-pin
pinout. It is not a diagnosis of the photographed hardware. Check supply-role
labels, IC orientation, rail grouping and wire pairing before changing physical
wiring. In particular the saved observations pair W4 with CLIP_BOTTOM/R4 and
W5 with R5/H30; those assignments should be checked against the actual wires.

Pin-role reference: [TI SN7400 datasheet, 14-pin top view and pin-function table](https://www.ti.com/lit/ds/symlink/sn7400.pdf).

## Remaining workflow details

The editable annotation file and exported netlist in `examples` now both use
revision 45. Recompiling the saved session reproduces the reviewed netlist
exactly, including endpoint provenance, rail groups and supply ports.

This artifact is a reviewed observation example, not a known-correct circuit,
model prediction, detector accuracy result, or full ML2 reasoning evaluation.
The existing NOT checker requires input/output roles and only supports an
isolated 7400, so it cannot certify this LED-loaded photo as-is.
