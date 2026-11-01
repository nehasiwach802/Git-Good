"""ML1-owned exports for the team's existing ML2 observation adapters.

No server, Android client, reference circuit, solver or product-memory calls.
"""

from copy import deepcopy

from .core import compile_netlist, validate
from .geometry import board_fingerprint


def reasoning_input(candidate, board):
    """Return an input spec accepted by ML2's existing generalized contract.

    v0.1 uses ML2's existing ml1_v0.1 adapter (including partial observations).
    Reviewed v0.2 and candidates with opamp/diode use internal_v1 so terminals
    aren't lost by the older adapter. These paths require complete review.
    """
    validate(candidate, board)
    extended_parts = any(c['part'] in ('diode', 'opamp') for c in candidate['components'])
    if candidate["schema_version"] == "0.1" and not extended_parts:
        return {"adapter": "ml1_v0.1", "payload": {"candidate": deepcopy(candidate), "board": deepcopy(board)}}
    netlist = compile_netlist(candidate, board)
    aliases = {"7400": "7400", "resistor": "R", "capacitor": "C", "led": "LED",
               "diode": "DIODE", "opamp": "OPAMP"}

    def point(target, node):
        source = netlist["provenance"][target]
        return {"net": node, "alternatives": [], "confirmed": source["confirmed"],
                "confidence": source["confidence"],
                "evidence_refs": [f"{candidate['candidate_id']}:r{candidate['revision']}:{target}"]}

    component_info = {c["id"]: c for c in candidate["components"]}
    components = []
    for component in netlist["components"]:
        original = component_info[component["id"]]
        passive = component["part"] in ("resistor", "capacitor")
        components.append({"id": component["id"], "model": aliases[component["part"]],
                           "identity_confirmed": original["identity_confirmed"],
                           "properties": {"value": original["value_si"]} if passive else {},
                           "properties_confirmed": False if component['part'] in ('opamp', 'diode') else original.get("value_confirmed", True),
                           "pins": {pin: point(component["id"]+"."+pin, node)
                                    for pin, node in component["pins"].items()}})
    observation = {"id": candidate["candidate_id"], "revision": candidate["revision"],
                   "reviewed_revision": candidate["reviewed_revision"],
                   "completeness_confirmed": candidate["board_confirmed"],
                   "components": components,
                   "ports": {p["id"]: point(p["id"], p["node"]) for p in netlist["ports"]},
                   "pending_evidence": [],
                   "source": {"adapter": "ml1_reviewed_extended" if extended_parts else "ml1_reviewed_v0.2", "board_id": board["id"],
                              "board_topology_id": board_fingerprint(board),
                              "image_sha256": candidate.get("image_sha256"),
                              "physical_schema_version": candidate['schema_version'],
                              "external_terminals": deepcopy(netlist.get("external_terminals", {})),
                              "endpoint_provenance": deepcopy(netlist["provenance"]),
                              "port_roles": {p["id"]: p["role"] for p in netlist["ports"]}}}
    return {"adapter": "internal_v1", "payload": observation}
