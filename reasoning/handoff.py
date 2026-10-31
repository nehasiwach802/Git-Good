"""Explicit identity mapping for already-converted reasoning-format circuits.

This is not a parser for ML1's draft 0.1 export: that schema and physical model
mapping must be read from the actual handoff before implementing such a parser.
No confidence, review status or electrical connection is inferred here.
"""
from copy import deepcopy
from .circuit import token
from .validation import ValidationError, validate_request


def prepare_reasoning_request(request, *, component_id_map, pin_maps=None):
    """Map student IDs/pins explicitly, preserving wrong wiring and confirmation.

    Source data must already use reasoning component types and SI values.
    Unmapped component IDs/pins are retained. Mapping to unknown reference IDs,
    colliding identities and incomplete pin renames are rejected.
    """
    if not isinstance(request, dict) or not isinstance(component_id_map, dict):
        raise ValidationError("$.component_id_map", "request and mapping must be objects")
    result = deepcopy(request)
    try:
        parts = result["student_circuit"]["components"]
        reference = result["experiment"]["circuit"]["components"]
        source_ids = [p["id"] for p in parts]
        reference_ids = {p["id"] for p in reference}
    except (KeyError, TypeError):
        raise ValidationError("$.student_circuit", "requires component objects and reference circuit") from None
    if len(source_ids) != len(set(source_ids)):
        raise ValidationError("$.student_circuit.components", "duplicate source IDs")
    if set(component_id_map) - set(source_ids):
        raise ValidationError("$.component_id_map", "mapping references unknown source components")
    if pin_maps is None:
        pin_maps = {}
    if not isinstance(pin_maps, dict) or set(pin_maps) - set(source_ids):
        raise ValidationError("$.pin_maps", "must map known source component IDs")
    used = set()
    for part in parts:
        original = part["id"]
        target = component_id_map.get(original, original)
        token(target)
        if original in component_id_map and target not in reference_ids:
            raise ValidationError("$.component_id_map", "target is not a reference component")
        if target in used:
            raise ValidationError("$.component_id_map", "component identities must be one-to-one")
        used.add(target)
        part["id"] = target
        if original in pin_maps:
            rename = pin_maps[original]
            if not isinstance(rename, dict) or set(rename) != set(part.get("pins", {})):
                raise ValidationError("$.pin_maps", "pin map must cover every source pin")
            if not all(isinstance(value, str) for value in rename.values()):
                raise ValidationError("$.pin_maps", "target pin names must be strings")
            if len(set(rename.values())) != len(rename):
                raise ValidationError("$.pin_maps", "target pin names must be unique")
            part["pins"] = {rename[pin]: net for pin, net in part["pins"].items()}
    validate_request(result)
    return result
