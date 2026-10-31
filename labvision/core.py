"""Dependency-free candidate validation, revision handling and netlist compilation.

Draft v0.1 contract. Electrical observations are retained even when wiring is wrong.
"""

from copy import deepcopy
import math
import re


SCHEMA_VERSION = "0.1"
PART_PINS = {
    "7400": {str(i) for i in range(1, 15)},
    "resistor": {"1", "2"},
    "capacitor": {"1", "2"},
    "led": {"anode", "cathode"},
}
NAND_GATES = [("1", "2", "3"), ("4", "5", "6"),
              ("9", "10", "8"), ("12", "13", "11")]


class CandidateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CandidateError(message)


def board_groups(board):
    """Explicit groups also allow real profiles to describe split power rails."""
    require(isinstance(board, dict), "board must be an object")
    require(isinstance(board.get("id"), str) and board["id"], "board.id required")
    groups = board.get("groups")
    require(isinstance(groups, list) and groups, "board.groups must be nonempty")
    mapping = {}
    for group in groups:
        require(isinstance(group, list) and group, "board group must be nonempty")
        require(all(isinstance(hole, str) and hole for hole in group),
                "hole IDs must be nonempty strings")
        for hole in group:
            require(hole not in mapping, f"hole {hole} appears in multiple board groups")
            mapping[hole] = min(group)
    return mapping


def make_board(rows=63):
    require(type(rows) is int and 1 <= rows <= 100, "rows must be 1..100")
    return {
        "id": f"terminal-strips-{rows}-no-rails",
        "description": "Two five-hole terminal strips per row; power rails excluded.",
        "groups": [[f"{col}{row}" for col in cols]
                   for row in range(1, rows + 1) for cols in ("ABCDE", "FGHIJ")],
    }


def endpoint(hole=None, source="manual", confidence="unknown"):
    return {"hole": hole, "alternatives": [], "confidence": confidence,
            "reason": "", "source": source, "confirmed": False}


def endpoints(candidate):
    for component in candidate["components"]:
        for pin, point in component["pins"].items():
            yield f"{component['id']}.{pin}", point, True
    for wire in candidate["wires"]:
        for side in ("a", "b"):
            yield f"{wire['id']}.{side}", wire[side], True
    for port in candidate["ports"]:
        yield port["id"], port["endpoint"], False


def validate(candidate, board):
    require(isinstance(candidate, dict), "candidate must be an object")
    require(candidate.get("schema_version") == SCHEMA_VERSION, "unsupported schema_version")
    require(isinstance(candidate.get("candidate_id"), str) and candidate["candidate_id"],
            "candidate_id required")
    revision = candidate.get("revision")
    require(type(revision) is int and revision >= 1, "revision must be a positive integer")
    holes = board_groups(board)
    require(candidate.get("board_profile_id") == board["id"], "board profile mismatch")
    require(type(candidate.get("board_confirmed")) is bool, "board_confirmed must be boolean")
    reviewed = candidate.get("reviewed_revision")
    require(reviewed is None or (type(reviewed) is int and reviewed == revision),
            "reviewed_revision is stale or invalid")
    for field in ("components", "wires", "ports", "issues"):
        require(isinstance(candidate.get(field), list), f"{field} must be a list")
    require(candidate["components"], "at least one component required")
    require(all(isinstance(issue, str) for issue in candidate["issues"]),
            "issues must contain strings")
    ids = set()
    for item in candidate["components"] + candidate["wires"] + candidate["ports"]:
        require(isinstance(item, dict), "items must be objects")
        name = item.get("id")
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name),
                "IDs must start with a letter; use letters, digits, '-' and '_'")
        require(name not in ids, f"duplicate ID: {name}")
        ids.add(name)
    for component in candidate["components"]:
        part = component.get("part")
        require(isinstance(part, str) and part in PART_PINS, f"unsupported part: {part}")
        require(type(component.get("identity_confirmed")) is bool,
                f"{component['id']}: identity_confirmed must be boolean")
        pins = component.get("pins")
        require(isinstance(pins, dict) and set(pins) == PART_PINS[part],
                f"{component['id']}: pin names must match {part}")
        if part in ("resistor", "capacitor"):
            value = component.get("value_si")
            require(value is None or (type(value) in (int, float)
                    and math.isfinite(value) and value > 0), "value_si must be positive or null")
            require(type(component.get("value_confirmed")) is bool,
                    "value_confirmed must be boolean")
    for wire in candidate["wires"]:
        require("a" in wire and "b" in wire, f"{wire['id']}: wire endpoints missing")
    for port in candidate["ports"]:
        require(port.get("role") in ("input", "output", "vcc", "gnd"), "invalid port role")
        require("endpoint" in port, "port endpoint required")
    occupied = {}
    for name, point, physical in endpoints(candidate):
        require(isinstance(point, dict), f"{name}: endpoint must be an object")
        hole = point.get("hole")
        require(hole is None or (isinstance(hole, str) and hole in holes),
                f"{name}: invalid hole {hole}")
        alternatives = point.get("alternatives")
        require(isinstance(alternatives, list) and all(isinstance(h, str) and h in holes
                for h in alternatives), f"{name}: invalid alternatives")
        require(point.get("confidence") in ("likely", "uncertain", "unknown"),
                f"{name}: invalid confidence")
        require(point.get("source") in ("vision", "manual"), f"{name}: invalid source")
        require(isinstance(point.get("reason"), str), f"{name}: reason must be text")
        require(type(point.get("confirmed")) is bool, f"{name}: confirmed must be boolean")
        if hole is not None and physical:
            require(hole not in occupied, f"{hole}: two physical endpoints occupy the same hole")
            occupied[hole] = name
    return candidate


def pending(candidate, board):
    validate(candidate, board)
    result = []
    if not candidate["board_confirmed"]:
        result.append("board topology/orientation not confirmed")
    for component in candidate["components"]:
        if not component["identity_confirmed"]:
            result.append(f"{component['id']}: identity/orientation not confirmed")
        if component["part"] in ("resistor", "capacitor") and (
                component.get("value_si") is None or not component["value_confirmed"]):
            result.append(f"{component['id']}: value not confirmed")
    for name, point, _ in endpoints(candidate):
        if point["hole"] is None:
            result.append(f"{name}: unknown hole")
        elif not point["confirmed"] or point["alternatives"]:
            result.append(f"{name}: review required")
    if not candidate["ports"]:
        result.append("external port assignments required")
    if candidate["reviewed_revision"] != candidate["revision"]:
        result.append("whole-circuit review required")
    return result


def correct(candidate, board, target, hole, expected_revision):
    validate(candidate, board)
    require(candidate["revision"] == expected_revision, "stale revision")
    result = deepcopy(candidate)
    matches = [p for name, p, _ in endpoints(result) if name == target]
    require(len(matches) == 1, f"unknown endpoint: {target}")
    matches[0].update(hole=hole, alternatives=[], confidence="likely", source="manual",
                      reason="student correction", confirmed=True)
    result["revision"] += 1
    result["reviewed_revision"] = None
    validate(result, board)
    return result


def confirm(candidate, board, expected_revision):
    """Caller explicitly acknowledges reviewing ALL observations and board topology."""
    require(not board.get("unverified_rail_holes"),
            "Rail connectivity is unverified; define actual connected groups and clear unverified_rail_holes before review")
    validate(candidate, board)
    require(candidate["revision"] == expected_revision, "stale revision")
    result = deepcopy(candidate)
    for name, point, _ in endpoints(result):
        require(point["hole"] is not None, f"{name}: resolve unknown hole before review")
        require(not point["alternatives"], f"{name}: resolve alternatives before review")
        point["confirmed"] = True
    for component in result["components"]:
        component["identity_confirmed"] = True
        if component["part"] in ("resistor", "capacitor"):
            require(component.get("value_si") is not None, "enter component values before review")
            component["value_confirmed"] = True
    result["board_confirmed"] = True
    result["reviewed_revision"] = result["revision"]
    validate(result, board)
    return result


def compile_netlist(candidate, board):
    require(not board.get("unverified_rail_holes"),
            "Rail connectivity is unverified; cannot compile a reviewed netlist")
    unresolved = pending(candidate, board)
    require(not unresolved, "Cannot export: " + "; ".join(unresolved))
    groups = board_groups(board)
    parent = {name: name for name in set(groups.values())}

    def root(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for wire in candidate["wires"]:
        a, b = root(groups[wire["a"]["hole"]]), root(groups[wire["b"]["hole"]])
        parent[max(a, b)] = min(a, b)
    used = {root(groups[p["hole"]]) for _, p, _ in endpoints(candidate)}
    nodes = {group: f"N{i}" for i, group in enumerate(sorted(used))}

    def node(point):
        return nodes[root(groups[point["hole"]])]

    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate["candidate_id"], "revision": candidate["revision"],
        "board_profile_id": board["id"], "status": "reviewed_connectivity",
        "components": [{"id": c["id"], "part": c["part"],
                        "value_si": c.get("value_si"),
                        "pins": {pin: node(p) for pin, p in c["pins"].items()}}
                       for c in candidate["components"]],
        "ports": [{"id": p["id"], "role": p["role"], "node": node(p["endpoint"])}
                  for p in candidate["ports"]],
        "nodes": {n: sorted(h for h, g in groups.items() if root(g) == group)
                  for group, n in nodes.items()},
        "provenance": {name: deepcopy(p) for name, p, _ in endpoints(candidate)},
        "issues": list(candidate["issues"]),
        "limitations": ["Reviewed observations do not verify physical continuity or device health.",
                        "Node IDs are local to this revision; compare graph connectivity."],
    }
