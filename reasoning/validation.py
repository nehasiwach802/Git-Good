"""Dependency-free request validation with stable field paths and error codes."""
from .circuit import PINS, normalize, number, token


class ValidationError(ValueError):
    def __init__(self, path, detail, code="invalid_field"):
        self.path, self.detail, self.code = path, detail, code
        super().__init__(f"{path}: {detail}")


def validate_request(request):
    """Validate the complete request before any confirmation gate or subprocess."""
    def fail(path, detail):
        raise ValidationError(path, detail)

    def obj(value, path):
        if not isinstance(value, dict):
            fail(path, "must be an object")
        return value

    def array(value, path, maximum):
        if not isinstance(value, list) or len(value) > maximum:
            fail(path, f"must be an array of at most {maximum} items")
        return value

    def numeric(value, path, positive=False, nonnegative=False):
        try:
            result = number(value, path, positive)
        except (ValueError, OverflowError):
            fail(path, "must be a finite number" + (" greater than zero" if positive else ""))
        if nonnegative and result < 0:
            fail(path, "must be nonnegative")

    def name(value, path):
        try:
            token(value)
        except ValueError:
            fail(path, "must be a valid circuit identifier")

    obj(request, "$")
    if request.get("schema_version") != "1.0":
        if request.get("schema_version") == "0.1" and request.get("status") == "reviewed_connectivity":
            raise ValidationError("$.schema_version",
                                  "ML1 reviewed_connectivity requires explicit component/model conversion; it is not a reasoning request",
                                  "vision_conversion_required")
        fail("$.schema_version", "must be 1.0")
    experiment = obj(request.get("experiment"), "$.experiment")
    for path, circuit in (("$.experiment.circuit", experiment.get("circuit")),
                          ("$.student_circuit", request.get("student_circuit"))):
        obj(circuit, path)
        array(circuit.get("components"), path + ".components", 100)
        array(circuit.get("wires", []), path + ".wires", 1000)
        for i, component in enumerate(circuit["components"]):
            obj(component, f"{path}.components[{i}]")
            kind = component.get("type")
            if isinstance(kind, str) and kind not in PINS:
                raise ValidationError(f"{path}.components[{i}].type",
                                      "supported analog models: R, C, V, OPAMP; digital ICs including 7400 need a separate model",
                                      "unsupported_component_model")
        try:
            normalize(circuit)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
            fail(path, str(exc))
    probes = array(experiment.get("probes"), "$.experiment.probes", 20)
    if not probes:
        fail("$.experiment.probes", "must contain at least one probe")
    ids = set()
    for i, probe in enumerate(probes):
        path = f"$.experiment.probes[{i}]"
        obj(probe, path)
        name(probe.get("id"), path + ".id")
        if probe["id"] in ids:
            fail(path + ".id", "duplicate probe ID")
        ids.add(probe["id"])
        name(probe.get("positive"), path + ".positive")
        name(probe.get("negative", "0"), path + ".negative")
        numeric(probe.get("frequency_hz"), path + ".frequency_hz", positive=True)
        for key, default in (("relative_tolerance", .05), ("absolute_tolerance_v", .01)):
            numeric(probe.get(key, default), path + "." + key, nonnegative=True)
    measurements = array(request.get("measurements", []), "$.measurements", 20)
    seen = set()
    for i, m in enumerate(measurements):
        path = f"$.measurements[{i}]"
        obj(m, path)
        name(m.get("probe_id"), path + ".probe_id")
        if m["probe_id"] not in ids or m["probe_id"] in seen:
            fail(path + ".probe_id", "unknown or duplicate probe ID")
        seen.add(m["probe_id"])
        if m.get("unit") != "V" or m.get("convention") != "ac_magnitude":
            fail(path, "requires unit V and convention ac_magnitude")
        numeric(m.get("value"), path + ".value", nonnegative=True)
    for key in ("student_expectations", "student_probe_nodes"):
        values = obj(request.get(key, {}), "$." + key)
        for pid, value in values.items():
            path = f"$.{key}.{pid}"
            if pid not in ids:
                fail(path, "unknown probe ID")
            if key == "student_expectations":
                numeric(value, path, nonnegative=True)
            else:
                obj(value, path)
                if set(value) - {"positive", "negative"}:
                    fail(path, "only positive and negative node overrides allowed")
                for pin, net in value.items():
                    name(net, path + "." + pin)
    equipment = obj(request.get("equipment_evidence", {}), "$.equipment_evidence")
    if "anomaly_follows_equipment" in equipment and not isinstance(equipment["anomaly_follows_equipment"], bool):
        fail("$.equipment_evidence.anomaly_follows_equipment", "must be boolean")
    if "source_ids" in equipment:
        sources = array(equipment["source_ids"], "$.equipment_evidence.source_ids", 100)
        if not all(isinstance(s, str) and 0 < len(s) <= 200 for s in sources):
            fail("$.equipment_evidence.source_ids", "requires nonempty strings up to 200 characters")
    if equipment.get("anomaly_follows_equipment") and not equipment.get("source_ids"):
        fail("$.equipment_evidence.source_ids", "required for substitution evidence")
    if "source_context" in request:
        source = obj(request["source_context"], "$.source_context")
        for field in ("candidate_revision", "reviewed_revision"):
            revision = source.get(field)
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                fail("$.source_context." + field, "must be a nonnegative integer")
        if not isinstance(source.get("board_id"), str) or not 0 < len(source["board_id"]) <= 200:
            fail("$.source_context.board_id", "requires a nonempty board identifier up to 200 characters")
    return request
