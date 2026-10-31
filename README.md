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

Install ngspice separately and put its executable on PATH to enable simulation.
Without it, requests still compare topology and explicitly report unavailable
predictions. Real solver tests are skipped when it is absent. See the
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
