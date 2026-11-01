# Work independently of vision and final experiments

Update: ML1's actual labvision package from Abhiram db8a1ce is now available in
this checkout and integrated through explicit digital/analog candidate routes.
Use `python tools/demo.py` for end-to-end dummy JSON and `python tools/run_checks.py`
for all tests with skipped tests treated as failures. See
[current integration notes](ML1_INTEGRATION_REVIEW.md). Earlier statements below
about independent fixture work still apply; real-photo accuracy remains unverified.

This implementation is a development baseline, not a finalized experiment list.
RC and ideal op-amp examples are simulated fixtures. Use handwritten JSON until
ML1 can produce the same electrical circuit representation.

## Local tools

```powershell
python -m reasoning examples/rc.json --validate-only
python -m reasoning examples/rc.json
python -m reasoning examples/rc.json --output result.json
python -m unittest discover -s tests -v
```

The CLI exits 2 for input/file errors. Simulation unavailability is an ordinary
diagnostic response, not a fabricated successful prediction. Optional test extras
(`python -m pip install -e ".[test]"`) enable JSON Schema validation tests. The
runtime does not need that dependency. Run commands from the repository root.

The GitHub Actions workflow installs ngspice on Ubuntu and runs the suite on
Python 3.11 and 3.14 when pushed. Adding the workflow does not mean CI has run.
Real solver tests are skipped locally without ngspice. Adapter tests mock process
execution; labeled scenarios use explicit synthetic oracle readings and do not
establish physical accuracy. The adapter disables user startup scripts using
ngspice's documented -n option, generates opaque internal net names to preserve
case distinctions and validates returned row shape, frequency and magnitude.
See the [ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf).

## Session integration without a database

```python
from reasoning.session import advance_session

first = advance_session(request)
# Store first["state"] in the backend's authorized session store.
# After the student changes the circuit or supplies observations:
second = advance_session(updated_request, first["state"])
```

History stores diagnostic results, not copies of the raw request. It still may
contain measurements, expectations and source references; the product backend
must apply its own session access and retention policy. No product datapack is
read or written by the coding agent or this helper.

unchanged_input tells the UI that no input evidence changed. It is not a claim
that a diagnostic check was completed. A repeated input can produce a new history
entry if solver availability/output changes. The helper does not skip a required
check simply because it was displayed before.

## Available integration examples

- examples/rc.json and examples/opamp.json: full diagnostic requests.
- examples/responses/needs-confirmation.json: confirmation UI mock.
- examples/responses/rc-solver-unavailable.json: unavailable-solver UI mock.
- schemas/: structural request and response contracts.
- tests/fixtures/diagnostic_cases.json: labeled, simulated reasoning cases,
  including multiple causes; not an equipment-fault training dataset.

## Decisions still needed with the team

1. Final experiments, physical devices, input conditions and required analyses.
2. ML1's stable component identity assignment and uncertain-connection proposal.
   Per-connection uncertainty, image bounding boxes and image provenance remain
   proposed extensions; component-level confirmation is the current interface.
3. Instructor-approved probes/checks, tolerances and low-voltage authorization.
4. Instrument/channel metadata and ML3's provenance/aggregation semantics.
5. Backend deployment, authentication, session storage and retention.

After those decisions, extend the contract with a versioned migration when
needed. Do not treat model confidence as student confirmation, repeated anomalies
as substitution evidence, or display a priority-rule check as information gain.
Realistic device models, DC/transient/phase modes, calibrated probabilities and
experiment-specific diagnostic actions are intentionally deferred until their
requirements and validation data are available.
