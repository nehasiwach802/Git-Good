"""Versioned internal observations: partial evidence is valid, not simulator input."""
from copy import deepcopy
from .registry import MODELS
from .validation import ValidationError
from .circuit import number, token


def fail(path, detail):
    raise ValidationError(path, detail)


def text(value, path):
    if not isinstance(value, str) or not 0 < len(value) <= 200:
        fail(path, "requires a nonempty string of at most 200 characters")


def object_(value, path):
    if not isinstance(value, dict):
        fail(path, "requires an object")


def revision(value, path):
    if type(value) is not int or value < 1:
        fail(path, "requires a positive integer")


def endpoint(point, path):
    object_(point, path)
    if "net" not in point:
        fail(path + ".net", "required; use null for unknown")
    if point["net"] is not None:
        text(point["net"], path + ".net")
    alternatives = point.get("alternatives", [])
    if (not isinstance(alternatives, list) or len(alternatives) > 10
            or any(not isinstance(n, str) or not 0 < len(n) <= 200 for n in alternatives)
            or len(set(alternatives)) != len(alternatives)):
        fail(path + ".alternatives", "requires up to 10 distinct net IDs")
    if type(point.get("confirmed", False)) is not bool:
        fail(path + ".confirmed", "requires boolean")
    if point.get("confidence", "unknown") not in ("likely", "uncertain", "unknown"):
        fail(path + ".confidence", "requires an uncalibrated confidence label")
    refs = point.get("evidence_refs", [])
    if not isinstance(refs, list) or len(refs) > 100:
        fail(path + ".evidence_refs", "requires up to 100 evidence references")
    for ref in refs:
        text(ref, path + ".evidence_refs")
    return point


def validate_observation(value):
    object_(value, "$.observation")
    text(value.get("id"), "$.observation.id")
    revision(value.get("revision"), "$.observation.revision")
    reviewed = value.get("reviewed_revision")
    if reviewed is not None:
        revision(reviewed, "$.observation.reviewed_revision")
        if reviewed > value["revision"]:
            fail("$.observation.reviewed_revision", "cannot review a future revision")
    if type(value.get("completeness_confirmed", False)) is not bool:
        fail("$.observation.completeness_confirmed", "requires boolean")
    components = value.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 100:
        fail("$.observation.components", "requires 1..100 components")
    ids = set()
    for i, component in enumerate(components):
        path = f"$.observation.components[{i}]"
        object_(component, path)
        text(component.get("id"), path + ".id")
        if component["id"] in ids:
            fail(path + ".id", "duplicate component ID")
        ids.add(component["id"])
        text(component.get("model"), path + ".model")
        for field in ("identity_confirmed", "properties_confirmed"):
            if type(component.get(field, False)) is not bool:
                fail(path + "." + field, "requires boolean")
        pins = component.get("pins")
        object_(pins, path + ".pins")
        if not 1 <= len(pins) <= 100:
            fail(path + ".pins", "requires 1..100 pins")
        model = MODELS.get(component["model"])
        if model and set(pins) != set(model.pins):
            fail(path + ".pins", "pin set does not match the declared model")
        for pin, point in pins.items():
            text(pin, path + ".pins")
            endpoint(point, path + ".pins." + pin)
        properties = component.get("properties", {})
        object_(properties, path + ".properties")
        if len(properties) > 20:
            fail(path + ".properties", "at most 20 properties")
        if model and set(properties) - set(model.properties):
            fail(path + ".properties", "unknown property for declared model")
        for key, prop in properties.items():
            text(key, path + ".properties")
            if prop is not None:
                number(prop, path + ".properties." + key, key in ("value", "gain"))
    ports = value.get("ports", {})
    object_(ports, "$.observation.ports")
    if len(ports) > 100:
        fail("$.observation.ports", "at most 100 ports")
    for name, point in ports.items():
        text(name, "$.observation.ports")
        endpoint(point, "$.observation.ports." + name)
    pending = value.get("pending_evidence", [])
    if not isinstance(pending, list) or len(pending) > 1000:
        fail("$.observation.pending_evidence", "at most 1000 evidence references")
    for ref in pending:
        text(ref, "$.observation.pending_evidence")
    if "source" in value:
        object_(value["source"], "$.observation.source")
        if "board_id" in value["source"]:
            text(value["source"]["board_id"], "$.observation.source.board_id")
    return value


def resolved(point):
    return point["net"] is not None and point.get("confirmed", False) and not point.get("alternatives")


def validate_reference(record):
    if (isinstance(record, dict) and isinstance(record.get("analysis"), dict)
            and record["analysis"].get("engine") == "wire_connections"):
        from .wires import validate_reference
        return validate_reference(record)
    object_(record, "$.reference")
    text(record.get("experiment_id"), "$.reference.experiment_id")
    text(record.get("version"), "$.reference.version")
    if record.get("approval") not in ("approved", "draft"):
        fail("$.reference.approval", "requires approved or draft")
    circuit = record.get("circuit")
    object_(circuit, "$.reference.circuit")
    parts = circuit.get("components")
    if not isinstance(parts, list) or not 1 <= len(parts) <= 100:
        fail("$.reference.circuit.components", "requires 1..100 components")
    seen = set()
    nets = set()
    for part in parts:
        object_(part, "$.reference.circuit.components")
        token(part.get("id"))
        if part["id"] in seen:
            fail("$.reference.circuit", "duplicate component ID")
        seen.add(part["id"])
        text(part.get("type"), "$.reference.circuit.type")
        object_(part.get("pins"), "$.reference.circuit.pins")
        if not 1 <= len(part["pins"]) <= 100:
            fail("$.reference.circuit.pins", "requires 1..100 pins")
        model = MODELS.get(part["type"])
        if model and set(part["pins"]) != set(model.pins):
            fail("$.reference.circuit.pins", "pin set does not match model")
        for pin, net in part["pins"].items():
            text(pin, "$.reference.circuit.pin")
            token(net)
            nets.add(net)
        for prop in model.properties if model else ():
            number(part.get(prop), "$.reference.circuit." + prop, prop in ("value", "gain"))
    if "wires" in circuit and (not isinstance(circuit["wires"], list) or circuit["wires"]):
        fail("$.reference.circuit.wires", "reference must use resolved electrical nets, not wire aliases")
    object_(record.get("ports", {}), "$.reference.ports")
    for port, net in record.get("ports", {}).items():
        text(port, "$.reference.ports")
        if not isinstance(net, str) or net not in nets:
            fail("$.reference.ports", "port must reference a circuit net")
    object_(record.get("analysis"), "$.reference.analysis")
    text(record["analysis"].get("engine"), "$.reference.analysis.engine")
    checks = record.get("approved_checks", [])
    if not isinstance(checks, list) or len(checks) > 50:
        fail("$.reference.approved_checks", "at most 50 check definitions")
    check_ids = set()
    for check in checks:
        object_(check, "$.reference.approved_checks")
        for key in ("id", "kind", "instruction"):
            text(check.get(key), "$.reference.approved_checks." + key)
        if check["id"] in check_ids:
            fail("$.reference.approved_checks", "duplicate check ID")
        check_ids.add(check["id"])
    return record


class ExperimentCatalog:
    """Backend-supplied versioned records; no product memory or automatic approval."""
    def __init__(self, records):
        self._records = {}
        for record in records:
            validate_reference(record)
            key = (record["experiment_id"], record["version"])
            if key in self._records:
                raise ValueError("duplicate experiment ID/version")
            self._records[key] = deepcopy(record)

    def get(self, experiment_id, version):
        try:
            return deepcopy(self._records[(experiment_id, version)])
        except (KeyError, TypeError):
            raise ValidationError("$.experiment_id", "unknown experiment ID/version") from None

    def bind(self, request):
        """Resolve an ID-only request in the trusted backend, not in extraction."""
        object_(request, "$")
        if "reference" in request:
            fail("$.reference", "catalog requests must not override the reference")
        result = deepcopy(request)
        result["reference"] = self.get(result.pop("experiment_id", None), result.pop("experiment_version", None))
        return result
