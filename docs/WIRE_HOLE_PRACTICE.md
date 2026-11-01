# Wire-to-hole identification exercise

User-requested scope: identify the two insertion holes of each jumper wire.
This is a visual connection exercise with no voltage readings or SPICE analysis.
The local draft is `examples/wire-hole-practice.experiment.json`; it is not an
approved backend catalog record or an observed candidate.

## Physical setup

1. Use an unpowered breadboard with no components or supply clips.
2. Check its printed A-J column labels and row direction. The supplied profile
   covers central rows 1-30 only; outer rails are excluded from this exercise.
3. Insert three separated short jumpers: E5-F5, E12-F12, E20-F20. Keep their
   insertion points visible and avoid crossing wires. These are construction
   instructions, not predictions about an existing photo.
4. Record a steady 8-12 second video: pause overhead, then tilt slightly to each
   side. Keep the row labels and both ends visible. Upload through the existing app.

## Expected review flow

Reuse ML1 `process_video` with `known_parts=[]` and the verified board profile.
Use the selected frame's existing `endpoint_detection` proposals. The detector
finds wire-end regions; it does not establish wire count, endpoint pairing, or
exact insertion holes. Do not divide proposal count by two to count wires.

Calibrate this frame with four known hole centers and two additional independent
check holes, using the existing calibration/review functions. Correct each
proposal to the actual insertion point as necessary. Assign both ends to a wire
explicitly and confirm pairing. Existing `detector_review.assign_proposal` snaps
a proposal to the calibrated grid but keeps it unconfirmed. The local annotator
already supports this; phone controls must be verified by the Android owner.

Display reviewed results such as `W1: E5 <-> F5`. Before review, label results
as suggested holes. For occlusion or ambiguity, show unknown and request another
view or a correction. A different frame requires its own calibration and review.

## Demonstrate a real change

After the first run, move only the F12 end of the second wire to F13 and record
again. A successful observation changes that pair to E12-F13. Extract without
reference wiring, then compare unordered endpoint pairs against the reference.
Wire IDs and endpoint order are arbitrary. Missing/extra/unknown wires must be
reported separately; do not manufacture the expected three observations.

Exact-hole identification differs from electrical connectivity: A12 and E12
normally share a terminal strip, but they are different physical insertion holes.
Score exact holes separately from electrically equivalent connections.

## Integration ownership and current limits

ML1 supplies the existing detector, calibration, review and video functions plus
this exercise definition. ML2 owns registering an appropriate catalog mode and
skipping readings/simulation for detection-only sessions; Android owns displaying
and correcting the connection pairs. Do not represent this as a resistor or
7400 experiment just to pass catalog validation. No new backend route, deployed
catalog entry, or phone wire-only screen was added by this change.

Reference wiring must never be passed to vision extraction. Report unassisted
hole-identification results separately from results after manual correction.
