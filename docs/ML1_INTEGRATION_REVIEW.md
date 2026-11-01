# ML1 integration and dummy runs

Integration owner: Codex acting as ML person 2. ML1 source imported selectively
from Abhiram commit db8a1ce: labvision package, its fixtures, handoff and tests.
Shared README, context and instructions were preserved. This supersedes the
earlier Meko report that ML1 source was unavailable.

## Data flow

```
photo -> ML1 unreviewed candidate -> student review/correction
     -> candidate + verified board profile -> reasoning.api.diagnose_input
     -> ML1 pending/compile_netlist -> selected analysis -> evidence + next check
```

The reasoning stage calls no image provider. It never calls confirm() on user
data. Synthetic fixtures explicitly model completed review solely for testing.
An edited endpoint increments revision and returns to needs_confirmation until
the student explicitly reviews it. A reviewed export does not establish safety,
correct wiring, physical continuity or device health.

## Request routes

POST /v1/diagnose and `python -m reasoning FILE.json` share the same dispatcher.

- Existing analog 1.0 requests: omit analysis; format stays unchanged.
- `analysis: 7400_as_not`: candidate, board, optional component_id (U1), gate
  (integer 1..4), measurements and student_expectations. Each observation is
  `{ "input": 0, "output": 1 }` with integer binary values only. At most one row
  per input condition. This is the isolated 7400 logical model, not SPICE/TTL
  voltage analysis. The default diagnostic apparatus hypothesis stays unresolved.
- `analysis: analog_from_vision`: candidate, board and canonical experiment;
  component_id_map; explicit ground_port; voltage_sources; probe_ports; canonical
  analog measurements/expectations. Reviewed resistor/capacitor parts map to R/C.
  Explicit sources supply electrical settings not visible in a photograph. LED,
  7400 and unknown ICs are not silently converted to analog models.

All paths retain the instructor_approved_low_voltage workflow flag, which must
come from the authorized backend in production. HTTP is still a local development
service, not an authenticated production deployment.

The analog schema is schemas/diagnose-request.schema.json. The vision envelope
is schemas/vision-diagnose-request.schema.json and references the analog schema
by its urn ID for shared fields. Offline validators must register that schema;
tests/test_schemas.py demonstrates it. The response uses the existing schema plus
optional logic_check, vision_source and reviewed_connectivity provenance.

GET /health checks the server process. GET /capabilities reports analysis routes
and whether an ngspice executable can be located; actual solver health is verified
by the integration tests, not just executable discovery.

## Dummy JSON you can run

```powershell
python tools/demo.py
python -m reasoning examples/vision-7400.json
python -m reasoning examples/vision-7400-wrong-wire.json
python -m reasoning examples/vision-7400-unreviewed.json
python -m reasoning examples/vision-rc.json
```

The demo saves full responses under outputs/demo/ and prints these outcomes:

| Input | Expected outcome |
|---|---|
| vision-7400.json | evaluated; topology matches; truth table 0->1, 1->0 |
| vision-7400-wrong-wire.json | evaluated; wiring evidence; review_wiring |
| vision-7400-unreviewed.json | needs_confirmation; no circuit behavior prediction |
| vision-rc.json | evaluated; actual SPICE output approximately 0.70710678 V |

The RC fixture intentionally supplies a student expectation of 1 V and a reading
near 0.7071 V; it therefore supports a conceptual discrepancy and asks for an
explanation. That reading is synthetic input; the prediction is real ngspice.
Saved examples/responses/vision-*.json are generated development samples.

## Real solver and release checks

```powershell
python tools/run_checks.py
```

This fails for test failures AND skipped tests. It includes ML1's mocked-provider
tests, review/compiler tests, real RC/op-amp SPICE tests, vision-to-RC conversion,
all four 7400 gate pinouts, API/schema/CLI tests and diagnostic failure cases.

Executable discovery order: NGSPICE_EXECUTABLE, ngspice on PATH, then the optional
local Windows .tools/Spice64/bin/ngspice_con.exe. The downloaded local binary is
ignored and not distributed by this repository. Set NGSPICE_EXECUTABLE or install
ngspice on another machine; install `.[test]` to enable schema tests. CI installs
ngspice on Ubuntu and uses the no-skips runner.

Real testing exposed the invalid v(0) expression and fixed it to numeric zero.
Degenerate/singular solver results are rejected instead of becoming predictions.

## Remaining practical limits

- Real-photo reliability is unproven; ML1's first photo report did not obtain a
  full structured netlist. Provider failure/manual fallback tests are not photo
  accuracy measurements. No paid Gemini request was run for this integration.
- Isolated 7400 logic omits voltage thresholds, loading, timing and device faults;
  unused floating inputs trigger a setup check. Extra components return an
  unsupported-scope instructor review, not an invented wiring fault.
- Ideal op-amp simulation excludes supply rails/clipping. Analog measurements
  remain single-frequency AC magnitude, not DC/transient/phase.
- Exhaustive testing of every physical fault is impossible. Final experiment
  approval, labelled photos, bench validation, Android integration, auth and
  authoritative backend storage are still required before production use.

Session helper accepts both routes, blocks candidate/board switches and stale
revisions, and rejects physical edits without a revision increase. Review flags
may change at the same revision. Returned state needs authorized backend storage;
Meko semantic memory is not authoritative lossless session persistence.
