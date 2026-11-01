"""Observation adapters never receive reference wiring or grant student review."""
from copy import deepcopy
from labvision.core import validate, board_groups, endpoints, CandidateError
from .observations import validate_observation, fail, object_
from .checks import stable_id


def internal(payload):
    validate_observation(payload)
    return deepcopy(payload)


def ml1_v01(payload):
    object_(payload, "$.input.payload")
    candidate, board = payload.get("candidate"), payload.get("board")
    try:
        validate(candidate, board)
    except (CandidateError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        fail("$.input.payload", str(exc))
    groups = board_groups(board)
    if candidate['schema_version']!='0.1' or any(c['part'] not in ('resistor','capacitor','7400','led') for c in candidate['components']):
        fail('$.input.adapter','Use the ml1 adapter or labvision.handoff.reasoning_input for extended/external observations')
    parent = {n: n for n in groups.values()}
    def root(n):
        while parent[n] != n:
            n = parent[n]
        return n
    pending = []
    if not candidate["board_confirmed"]:
        pending.append("board_topology")
    uncertain_wires = False
    for wire in candidate["wires"]:
        for side in ("a", "b"):
            point = wire[side]
            if point["hole"] is None or point["alternatives"] or not point["confirmed"]:
                pending.append(wire["id"] + "." + side)
                uncertain_wires = True
        a, b = wire["a"]["hole"], wire["b"]["hole"]
        if a is not None and b is not None:
            a, b = root(groups[a]), root(groups[b])
            parent[max(a, b)] = min(a, b)
    def convert(point, source):
        # Nodes are primary observed proposals only. An uncertain jumper can
        # alter every derived relationship, so none are certified in that case.
        return {"net": root(groups[point["hole"]]) if point["hole"] is not None else None,
                "alternatives": sorted({root(groups[h]) for h in point["alternatives"]}),
                "confirmed": point["confirmed"] and candidate["board_confirmed"] and not uncertain_wires,
                "confidence": point["confidence"], "evidence_refs": [source]}
    aliases = {"resistor": "R", "capacitor": "C", "7400": "7400", "led": "LED"}
    result = {"id": candidate["candidate_id"], "revision": candidate["revision"],
              "reviewed_revision": candidate["reviewed_revision"],
              "completeness_confirmed": candidate["board_confirmed"] and candidate["reviewed_revision"] == candidate["revision"],
              "components": [], "ports": {}, "pending_evidence": pending,
              "source": {"adapter": "ml1_v0.1", "board_id": board["id"],
                         "board_topology_id": stable_id("board_", board["groups"]),
                         "endpoint_provenance": {name: deepcopy(p) for name, p, _ in endpoints(candidate)}}}
    for c in candidate["components"]:
        result["components"].append({"id": c["id"], "model": aliases[c["part"]],
            "identity_confirmed": c["identity_confirmed"],
            "properties": {"value": c.get("value_si")} if c["part"] in ("resistor", "capacitor") else {},
            "properties_confirmed": c.get("value_confirmed", True),
            "pins": {p: convert(point, c["id"] + "." + p) for p, point in c["pins"].items()}})
    result["ports"] = {p["id"]: convert(p["endpoint"], p["id"]) for p in candidate["ports"]}
    validate_observation(result)
    return result


def ml1(payload):
    """Let ML1 choose its version/part-specific handoff; never grant review."""
    from labvision.handoff import reasoning_input
    object_(payload,'$.input.payload')
    try:spec=reasoning_input(payload.get('candidate'),payload.get('board'))
    except (CandidateError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        fail('$.input.payload',str(exc))
    return internal(spec['payload']) if spec['adapter']=='internal_v1' else ml1_v01(spec['payload'])


ADAPTERS = {"internal_v1": internal, "ml1_v0.1": ml1_v01, "ml1":ml1}


def adapt_request(request):
    if not isinstance(request, dict):
        fail("$", "requires an object")
    result = deepcopy(request)
    if "input" in result:
        if "observation" in result:
            fail("$.input", "provide input adapter or observation, not both")
        spec = result.pop("input")
        object_(spec, "$.input")
        name = spec.get("adapter")
        if not isinstance(name, str) or name not in ADAPTERS:
            fail("$.input.adapter", "unsupported observation adapter")
        result["observation"] = ADAPTERS[name](spec.get("payload"))
    if "port_map" in result:
        mapping = result.pop("port_map")
        object_(mapping, "$.port_map")
        observation = result.get("observation")
        object_(observation, "$.observation")
        validate_observation(observation)
        ports = observation.get("ports", {})
        object_(ports, "$.observation.ports")
        object_(result.get("reference"), "$.reference")
        declared = result["reference"].get("ports", {})
        if not isinstance(declared, dict) or set(mapping) - set(ports):
            fail("$.port_map", "mapping requires known source ports and declared reference ports")
        renamed = {}
        for name, point in ports.items():
            target = mapping.get(name, name)
            if not isinstance(target, str) or (name in mapping and target not in declared):
                fail("$.port_map", "mapped port must name a declared reference port")
            if target in renamed:
                fail("$.port_map", "port correspondence must be one-to-one")
            renamed[target] = point
        observation["ports"] = renamed
        observation.setdefault("source", {})["port_map"] = deepcopy(mapping)
    return result
