# Reasoning contract v1.0

Generalized requests now use version 2.0 alongside this retained 1.0 interface.
See docs/GENERALIZED_CORE.md and schemas/generalized-request.schema.json. The
internal observation schema and adapters deliberately separate ML1 format details
from comparison, uncertainty, model capabilities and experiment references.

Current integration adds explicit ML1 candidate envelopes alongside this legacy
analog request. See docs/ML1_INTEGRATION_REVIEW.md and
schemas/vision-diagnose-request.schema.json. Both use POST /v1/diagnose and the
shared reasoning.api.diagnose_input dispatcher; reasoning.engine.diagnose remains
the analog-only function for compatibility. A raw 0.1 export is still not a full
diagnostic request. No analysis is inferred from a component name.

ML1 code is imported from Abhiram db8a1ce. The 7400_as_not path performs isolated
logical topology/truth-table checks; the analog_from_vision path requires explicit
source settings, ground/probe port mappings and supported R/C models. Both enforce
the ML1 review gate and preserve endpoint provenance. Neither invokes Gemini or
grants human review. See tools/demo.py for synthetic reproducible examples.

Decision owner: Codex acting as ML person 2. Integration contract for teammates.

POST /v1/diagnose accepts the JSON illustrated in examples/rc.json and
examples/opamp.json. GET /health reports process readiness, not solver readiness.
No product memory is accessed by this package.

All component IDs must be stable between reference and student circuits. ML1
must supply the instructor component IDs, confirmed pin-to-net assignments and
wire aliases. R/C pins are 1 and 2; V pins are + and -; OPAMP pins are +, -, out,
vcc and vee. Values are finite numeric SI units (ohms, farads, volts); engineering
strings such as 1k are rejected. Ground is 0. Supported component types are
R, C, V and OPAMP. Unsupported devices require a new validated model.

Confirmation is per component and means every pin has been confirmed by the
student. Omitted confirmation is false. Normalize breadboard rails/holes through
wires, a list of two-net lists. Net names otherwise carry no identity during diff.
Connectivity differences report a general mismatch, with additional
missing_connection/unexpected_connection terminal evidence when correspondence
is unambiguous. Ambiguous passive terminals are deliberately omitted from
localization. These are inspection findings, not instructions to move wires.
This engine does not infer component identity from images.

Each probe includes id, positive, negative, frequency_hz and optional
relative_tolerance and absolute_tolerance_v. Tolerance is the larger of the
absolute and relative bounds; defaults are 0.01 V and 5 percent. These are
configured acceptance bounds, not statistical confidence intervals. Measurement
unit must be V and convention ac_magnitude. Sources specify DC bias and AC
small-signal magnitude. This version does not support transient, RMS/Vpp
conversion or measured phase. Student expectations use the same convention.

If student nets use different labels, student_probe_nodes maps probe IDs to
objects containing positive and negative student net names. ML1/backend must
provide this explicitly; circuit equivalence does not establish unique probe
identity in a symmetric circuit.

The backend must only set safety_profile=instructor_approved_low_voltage after
validating the session against the instructor's approved workflow. It is not a
voltage detector or a safety certification. The HTTP server is local development
infrastructure without authentication; use a gateway for remote deployment.

ML3 may provide equipment_evidence with anomaly_follows_equipment=true and
nonempty source_ids after an approved substitution check. This supports suspicion
only; no automatic equipment condemnation or shared-knowledge promotion occurs.
Repeated session anomalies alone must not set this flag.

Response includes status, findings with evidence IDs, reference/student
predictions, hypotheses, next_check and limitations. Hypotheses are independent
ordinal supported/unresolved labels; multiple causes can coexist. Next checks
use a documented priority order (confirmation, wiring, solver, missing readings,
setup, concept), not computed information gain. Missing/failed simulation never
constitutes apparatus evidence. The ideal op-amp VCVS ignores supply rails and
clipping; do not interpret its prediction as a supply-fault assessment.

Malformed requests return 400; bodies above 256 KiB return 413. Simulation status
can be ok, unavailable, invalid_probe, timeout or failed. No fallback values are
fabricated. Instructor content is structured data; raw SPICE is never accepted.

## Compatible implementation additions

Machine-readable Draft 2020-12 schemas are in schemas/diagnose-request.schema.json
and schemas/diagnose-response.schema.json. Runtime validation also checks rules
that JSON Schema alone does not express: unique IDs, measurement/probe references,
expectation/probe references and finite numbers. Extra object metadata is generally
allowed for compatibility; it does not change reasoning. The request format and
component-level confirmation remain unchanged pending team agreement.

Validation runs before any gate or simulation. Invalid input errors retain
error=invalid_request and add code, path and detail. Field validation uses
code=invalid_field; JSON/envelope parsing uses malformed_request. Duplicate JSON
keys and non-finite numeric literals are rejected.

Finding IDs are content-derived opaque identifiers, stable for unchanged evidence.
Clients must not parse their format or assume sequential IDs. Identical evidence
across different sessions may share an ID; scope it by the backend session ID.
next_check adds check_id, input_type, requires_instructor and evidence_ids. Check
IDs identify a check payload, not completion or authorization. Clients should
ignore unfamiliar response fields. Hypotheses retain all supporting evidence
instead of overwriting an earlier probe's finding.

reasoning.session.advance_session is an optional Python helper, not a new HTTP
contract. The backend supplies and stores returned state. No memory service is
called. History contains up to 100 diagnostic snapshots, with duplicate identical
input/result snapshots suppressed. Current diagnosis never inherits old support;
changed reference experiments require a new session. No automatic forgetting,
student identity management, check-completion claims or persistent store is added.
