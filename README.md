# Git-Good — AI Lab Mentor reasoning core

ML person 2 implementation: circuit validation and connectivity comparison,
ngspice AC predictions, evidence-linked diagnostic ledger and next-check rules.
Python 3.11+; the core and local HTTP server need no Python dependencies.

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m reasoning.server
```

Validate or diagnose a fixture directly:

```powershell
python -m reasoning examples/rc.json --validate-only
python -m reasoning examples/rc.json
```

The engine now validates full requests before simulation, provides stable evidence
and check IDs, and adds conservative terminal-level wiring evidence where possible.
An optional Python session helper preserves diagnostic snapshots without retaining
stale fault support. See [development and handoff notes](docs/development.md),
[JSON Schemas](schemas/diagnose-request.schema.json), and [sample responses](examples/responses/).

Send `examples/rc.json` or `examples/opamp.json` as a JSON POST body to
`http://127.0.0.1:8000/v1/diagnose`. Health: `GET /health`.

Install ngspice separately and put its executable on PATH, set NGSPICE_EXECUTABLE,
or use the optional local Windows .tools/Spice64/bin/ngspice_con.exe. Without a
solver, requests report unavailable predictions. The release test runner fails
if any test is skipped. See the
[official ngspice tutorial](https://ngspice.sourceforge.io/ngspice-tutorial.html).

Read [the teammate integration contract](docs/contract.md) before integrating.
The fixtures are simulated examples, not real student evidence. RC uses 1 kohm,
1 microfarad and a 1 V AC source at approximately the cutoff frequency, predicting
0.7071 V. The second fixture uses an ideal inverting op-amp with gain near -2;
only magnitude is evaluated. Supply saturation, phase, arbitrary devices and
transient readings are outside this version.

The local server is for development. Authentication, instructor workflow
authorization, vision, Android, memory storage and instructor review UI belong
to the shared backend or the other role owners.

ML1's labvision code and fixtures from Abhiram db8a1ce are integrated. The reasoning
dispatcher accepts reviewed candidates for isolated 7400 NAND-as-NOT logic and
explicit resistor/capacitor-to-SPICE conversion. Review is never granted by the
diagnostic API; real-photo extraction remains unverified.

Run the complete no-skips checks and the dummy JSON demo:

```powershell
python tools/run_checks.py
python tools/demo.py
python -m reasoning examples/vision-7400.json
python -m reasoning examples/vision-rc.json
```

The demo writes full responses to outputs/demo/. Correct 7400 wiring returns the
truth table 0 -> 1, 1 -> 0; wrong wiring requests review; unreviewed candidates
request confirmation; the RC example uses real ngspice and predicts about
0.70710678 V. See [integration and demo details](docs/ML1_INTEGRATION_REVIEW.md),
[ML1's handoff](docs/ML1_HANDOFF.md) and the
[vision request schema](schemas/vision-diagnose-request.schema.json).

GET /capabilities reports available analysis routes and solver discovery.

Generalized core (request version 2.0): independent observation adapters, partial
connection uncertainty, versioned reference records, explicit identity mapping,
and model/analysis capabilities. Existing 1.0 requests remain supported.

```powershell
python tools/demo_generalized.py
python -m reasoning examples/generalized/rc-uncertain.json
python -m reasoning examples/generalized/divider.json
```

See [generalized architecture and internal contract](docs/GENERALIZED_CORE.md).
Future ML1 output formats can be translated by an adapter; unresolved predictions
are not treated as confirmed student wiring mistakes.
