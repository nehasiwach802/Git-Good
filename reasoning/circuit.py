"""Validated circuit schema and net-name-independent connectivity comparison."""
import math
import re

TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$|^0$")
PINS = {"R": {"1", "2"}, "C": {"1", "2"}, "V": {"+", "-"},
        "OPAMP": {"+", "-", "out", "vcc", "vee"}}


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def token(value):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise ValueError("IDs and nets must be short alphanumeric identifiers")
    return value


def normalize(circuit):
    if not isinstance(circuit, dict):
        raise ValueError("circuit must be an object")
    components = circuit.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 100:
        raise ValueError("circuit requires 1..100 components")
    parent = {}

    def root(n):
        token(n)
        parent.setdefault(n, n)
        while parent[n] != n:
            n = parent[n]
        return n

    for wire in circuit.get("wires", []):
        if not isinstance(wire, list) or len(wire) != 2:
            raise ValueError("wire must contain two net names")
        a, b = map(root, wire)
        parent[max(a, b)] = min(a, b)
    result = []
    seen = set()
    for c in components:
        cid = token(c["id"])
        kind = c["type"]
        if cid in seen or kind not in PINS:
            raise ValueError("duplicate component ID or unsupported component type")
        seen.add(cid)
        if set(c["pins"]) != PINS[kind]:
            raise ValueError(f"invalid pins for {cid}")
        pins = {p: root(n) for p, n in c["pins"].items()}
        item = {"id": cid, "type": kind, "pins": pins,
                "confirmed": c.get("confirmed", False)}
        if not isinstance(item["confirmed"], bool):
            raise ValueError("confirmed must be boolean")
        if kind in {"R", "C"}:
            item["value"] = number(c["value"], "component value", True)
        elif kind == "V":
            item["dc"] = number(c.get("dc", 0), "dc")
            item["ac"] = number(c.get("ac", 0), "ac")
        else:
            item["gain"] = number(c.get("gain", 100000), "opamp gain", True)
        result.append(item)
    # Resolve aliases after every union, including aliases used by probes.
    for c in result:
        c["pins"] = {p: root(n) for p, n in c["pins"].items()}
    return {"components": result, "aliases": {n: root(n) for n in parent}}


def diff(reference, student):
    """Compare terminal partitions. R/C terminals are interchangeable.

    Stable component IDs are required. Net labels are deliberately ignored,
    except ground, which is an electrical anchor.
    """
    ref = {c["id"]: c for c in reference["components"]}
    got = {c["id"]: c for c in student["components"]}
    findings = []
    for cid in sorted(ref.keys() - got.keys()):
        findings.append({"kind": "missing_component", "component": cid})
    for cid in sorted(got.keys() - ref.keys()):
        findings.append({"kind": "extra_component", "component": cid})
    common = sorted(ref.keys() & got.keys())
    for cid in common:
        a, b = ref[cid], got[cid]
        if a["type"] != b["type"]:
            findings.append({"kind": "wrong_type", "component": cid})
        elif any(a.get(k) != b.get(k) for k in ("value", "dc", "ac", "gain")):
            findings.append({"kind": "wrong_value_or_source", "component": cid})

    # Backtracking node bijection avoids exponential enumeration of terminal swaps.
    mapping = {"0": "0"}
    reverse = {"0": "0"}
    states = [0]

    def match(index, forward, backward):
        states[0] += 1
        if states[0] > 20000:
            raise ValueError("connectivity comparison exceeds complexity limit")
        if index == len(common):
            return True
        cid = common[index]
        a, b = ref[cid], got[cid]
        if a["type"] != b["type"]:
            return False
        pins = sorted(a["pins"])
        options = [pins]
        if a["type"] in {"R", "C"}:
            options.append(list(reversed(pins)))
        for target in options:
            f, r = dict(forward), dict(backward)
            valid = True
            for p, q in zip(pins, target):
                x, y = a["pins"][p], b["pins"][q]
                if (x in f and f[x] != y) or (y in r and r[y] != x):
                    valid = False
                    break
                f[x], r[y] = y, x
            if valid and match(index + 1, f, r):
                return True
        return False

    if not match(0, mapping, reverse):
        findings.append({"kind": "connectivity_mismatch",
                         "detail": "Terminal connectivity or ground differs; inspect confirmed connections."})
        findings.extend(connection_evidence(ref, got))
    return findings


def connection_evidence(reference, student):
    """Report only relationships between unambiguous, anchored terminals.

    Passive pin swaps make fault localization ambiguous. A passive pin is
    anchored only when its net also contains a matching directional terminal
    (or ground), and exactly one of its pins has that anchor in the student.
    Unanchored cases retain the general mismatch instead of inventing a repair.
    """
    common = sorted(reference.keys() & student.keys())
    anchors_ref, anchors_got = {"0": {"ground"}}, {"0": {"ground"}}
    for cid in common:
        a, b = reference[cid], student[cid]
        if a["type"] != b["type"] or a["type"] in {"R", "C"}:
            continue
        for pin in a["pins"]:
            anchor = (cid, pin)
            anchors_ref.setdefault(a["pins"][pin], set()).add(anchor)
            anchors_got.setdefault(b["pins"][pin], set()).add(anchor)
    pairs = []
    for cid in common:
        a, b = reference[cid], student[cid]
        if a["type"] != b["type"]:
            continue
        for pin, net in a["pins"].items():
            target = pin
            if a["type"] in {"R", "C"}:
                anchor = anchors_ref.get(net, set())
                candidates = [q for q, n in b["pins"].items()
                              if anchor and anchor & anchors_got.get(n, set())]
                if len(candidates) != 1:
                    continue
                target = candidates[0]
            pairs.append(({"component": cid, "reference_pin": pin, "student_pin": target},
                          net, b["pins"][target]))
    pairs.append(({"component": None, "reference_pin": "ground", "student_pin": "ground"}, "0", "0"))
    findings = []
    for i, (a, ar, ag) in enumerate(pairs):
        for b, br, bg in pairs[i + 1:]:
            if (ar == br) == (ag == bg):
                continue
            findings.append({"kind": "missing_connection" if ar == br else "unexpected_connection",
                             "terminals": [a, b], "reference_connected": ar == br,
                             "student_connected": ag == bg})
            if len(findings) == 50:
                return findings
    return findings
