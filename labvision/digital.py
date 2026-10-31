"""Small, conservative NOT-from-NAND reference check for the ML1 handoff demo.

This is not SPICE or the team's full reasoning engine. It only checks one selected
7400 gate's reviewed topology and, when valid, its ideal Boolean truth table.
"""

from .core import NAND_GATES, require


def check_not(netlist, component_id="U1", gate=1):
    require(netlist.get("status") == "reviewed_connectivity", "reviewed netlist required")
    require(type(gate) is int and 1 <= gate <= 4, "gate must be 1..4")
    components = [c for c in netlist["components"] if c["id"] == component_id]
    require(len(components) == 1 and components[0]["part"] == "7400", "select a 7400")
    chip = components[0]
    pins = chip["pins"]
    issues = []
    warnings = []
    roles = {}
    for port in netlist["ports"]:
        roles.setdefault(port["role"], []).append(port)
    for role in ("input", "output", "vcc", "gnd"):
        if len(roles.get(role, [])) != 1:
            issues.append(f"Expected exactly one {role} port")
    if issues:
        return {"check": "7400_as_not", "topology_matches": False,
                "issues": issues, "warnings": [], "truth_table": []}
    ports = {role: items[0]["node"] for role, items in roles.items()}
    if len(set(ports.values())) != 4:
        issues.append("Input, output, VCC and GND must be distinct electrical nodes")
    if pins["14"] != ports["vcc"]:
        issues.append(f"{component_id}.14 is not connected to the VCC port")
    if pins["7"] != ports["gnd"]:
        issues.append(f"{component_id}.7 is not connected to the GND port")
    a, b, y = NAND_GATES[gate - 1]
    for pin in (a, b):
        if pins[pin] != ports["input"]:
            issues.append(f"{component_id}.{pin} must connect to the input for NAND-as-NOT")
    if pins[y] != ports["output"]:
        issues.append(f"{component_id}.{y} must connect to the output port")
    selected = {a, b, y}
    for index, (other_a, other_b, other_y) in enumerate(NAND_GATES, 1):
        if index == gate:
            continue
        for pin in (other_a, other_b):
            if pins[pin] not in (ports["gnd"], ports["vcc"]):
                warnings.append(f"Unused input {component_id}.{pin} is not tied to a supply node")
        if pins[other_y] in set(ports.values()) or any(
                pins[other_y] == pins[p] for p in selected):
            issues.append(f"Unused gate output {component_id}.{other_y} shares an active/supply node")
    # This intentionally conservative checker only certifies an isolated gate.
    if len(netlist["components"]) != 1:
        issues.append("Reference check supports an isolated 7400 only; additional components need ML2 evaluation")
    return {
        "check": "7400_as_not", "component_id": component_id, "gate": gate,
        "topology_matches": not issues, "issues": issues, "warnings": warnings,
        "truth_table": [{"input": a, "expected_output": 1 - (a & a)} for a in (0, 1)]
                       if not issues else [],
        "scope": "Ideal Boolean reference only; no measured voltage, timing, loading or device-health claim.",
    }
