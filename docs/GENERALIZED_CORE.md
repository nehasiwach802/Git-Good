# Generalized electronics reasoning core

Implementation owner: Codex acting as ML person 2. Request/response version 2.0
is an internal development contract, not a claim that ML1's future export format
is finalized. Existing version 1.0 routes and demos remain supported unchanged.

## Architecture

```
external observations -> named adapter -> internal partial observation
approved reference record + explicit identity/port correspondence
    -> uncertainty-aware comparison -> capability checks -> supported analysis
    -> findings, required confirmations, hypotheses and next check
```

adapters.py accepts only observation payloads; it never receives the reference
wiring. internal_v1 validates an already-internal observation. ml1_v0.1 translates
the current actual candidate + board format without calling confirm(). Unknown
holes remain null; alternatives remain proposals. Only board groups and observed
jumpers merge nets. An uncertain jumper can affect all derived connectivity, so
the adapter conservatively marks derived endpoints unconfirmed until resolved.
Board review and whole-capture review remain separate from electrical correctness.

observations.py defines partial observation validation and ExperimentCatalog.
registry.py declares supported models, required properties, pin semantics and
analysis capabilities. generalized.py coordinates comparison and engine routing;
it does not branch on experiment names. Existing analog and isolated digital
backends remain the supported behavior models. Adding a new experiment using
those capabilities requires a record, not a new experiment-specific code branch.
New device models/analyses still require implementation and independent tests.

## Internal representation

See examples/generalized/rc.json for a complete request. Its reference contains
experiment_id, version, approval, deterministic circuit, named ports, analysis
configuration and optional approved_checks. Unknown models/analyses yield explicit
capability gaps rather than fabricated predictions. Source settings and values
in a reference are explicit, including zero DC bias where appropriate.

The independent observation contains an ID/revision, reviewed_revision,
completeness_confirmed, components and named ports. Each component has a declared
model, identity_confirmed, properties, properties_confirmed and named pins.
Each pin/port endpoint has:

```json
{
  "net": null,
  "alternatives": [],
  "confirmed": false,
  "confidence": "unknown",
  "evidence_refs": ["capture-1:component-2:pin-1"]
}
```

Known models require all pins, with null for unobserved connections. Missing
properties are unresolved evidence, not implicit default values. Confidence labels
are uncalibrated and cannot grant confirmation. The full primary proposal is
never overwritten with a reference connection. Model identification and physical
IC pin interpretation must be verified upstream; unknown parts are not substituted.

component_map explicitly maps observed IDs to reference IDs. There is no automatic
match even when labels happen to be identical. A null mapping means an explicitly
extra component, not an unresolved identity. port_map optionally renames observed
ports to reference port identities; collisions and unknown targets are rejected.
Unmapped ports are expected to already use semantic reference port identities.
No net-name equality is assumed across reference/observed circuits: internal net
names are generated, and ground comes from an explicitly corresponding port.

## Comparison and attribution

- net=null: unknown_connection and a confirmation request, no invented connection.
- alternatives/unconfirmed primary mismatch: possible discrepancy, no wiring support.
- Confirmed type/value or fixed-terminal discrepancy: confirmed evidence can be
  shown even if another part of the capture is unresolved.
- Full resolved capture: graph comparison respects passive pin reversal and net
  renaming. Missing/extra components need complete capture/identity review before
  becoming confirmed findings. Unknown properties never become wrong values.
- Draft references cannot establish confirmed faults. Approved reference/workflow
  flags must come from the trusted backend, not be accepted as client authorization.

For partial circuits, terminal relationship localization is deliberately limited
to directional pins and known ports. Ambiguous passive-terminal relationships
remain unresolved until enough information is available. There is no exhaustive
enumeration of alternative circuits or calibrated posterior probabilities.

Behavioral analysis is blocked until review, identity, values, pins and required
ports are resolved. Native analysis engines are connectivity (no behavior),
analog_ac (R/C/V/ideal OPAMP) and 7400_as_not (isolated ideal Boolean logic).
Analog measurements retain V/ac_magnitude conventions. Digital observations are
integer binary rows, not voltages. Apparatus attribution remains conservative;
the analog runner accepts existing source-linked equipment_evidence. Digital
hardware fault diagnosis and general digital simulation are not implemented.

The response separates pending confirmations and capability_gaps from findings.
Findings can have certainty=confirmed, possible or unresolved. Only confirmed
discrepancies support wiring. The reported problem description is validated as
text but is not promoted to evidence or automatically interpreted as a fault.
Configured approved checks can enrich a matching generic next check; arbitrary
LLM procedures are not executed. Behavioral measurement findings retain backend
evidence fields; not every observation is a wiring-certainty statement.

## Backend lookup and sessions

```python
from reasoning.observations import ExperimentCatalog
from reasoning import diagnose_input

catalog = ExperimentCatalog(approved_records)
request = catalog.bind(id_only_request)  # experiment_id + experiment_version
result = diagnose_input(request)
```

Catalogs use explicit ID/version pairs, reject duplicate records, and return copies.
They are injected by the backend: the local HTTP service does not load arbitrary
files from user paths or automatically approve records. Inline references remain
useful for development. The engine does not yet select a final five experiments.

advance_session supports 2.0 using a distinct version-2 state. Reference/version/
analysis changes, observation identity switches and older revisions are rejected.
The capability registry version is also bound; updating model semantics requires
a version bump and a new session rather than reuse of earlier conclusions.
Physical changes require a revision increment; review flags may change at the
same revision. History is caller-stored and does not retain stale fault support.
Legacy version-1 state must not be mixed with version-2 requests.

## Run and inspect

```powershell
python tools/run_checks.py
python tools/demo_generalized.py
python -m reasoning examples/generalized/rc-uncertain.json
python -m reasoning examples/generalized/divider.json
```

Outputs are written to outputs/generalized/. RC and resistor divider share the
same analog backend: about 0.707106781 V and 0.5 V respectively. Uncertain and
unknown RC observations request confirmation with no wiring support. The ML1
fixture traverses its adapter and the generalized isolated-7400 backend.

POST /v1/diagnose dispatches by schema_version and accepts 2.0. GET /capabilities
advertises models and analyses. Structural contracts are schemas/observation,
reference-record, generalized-request and generalized-response.schema.json.
JSON Schema URN references require local registration (see test_schemas.py);
runtime checks additionally enforce identity references and model pin semantics.

Future ML1 field names require a new adapter or a change isolated to the existing
adapter. Agree on uncertainty, component identity, pin interpretation, provenance
and revisions with ML1 before calling any external format final. Physical/photo
validation, production authentication, persistent storage and ML3 orchestration
remain separate work.
