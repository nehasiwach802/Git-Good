"""Restricted ngspice AC adapter. No user-provided SPICE directives execute."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from .circuit import number, token


def find_ngspice():
    """Explicit environment setting, PATH, then the optional local Windows tool."""
    configured = os.environ.get("NGSPICE_EXECUTABLE")
    if configured:
        return shutil.which(configured)
    found = shutil.which("ngspice")
    if found:
        return found
    local = Path(__file__).resolve().parents[1] / ".tools" / "Spice64" / "bin" / "ngspice_con.exe"
    return str(local) if local.is_file() else None


def simulate(circuit, probe, executable=None):
    frequency = number(probe["frequency_hz"], "frequency_hz", True)
    positive, negative = token(probe["positive"]), token(probe.get("negative", "0"))
    positive = circuit["aliases"].get(positive, positive)
    negative = circuit["aliases"].get(negative, negative)
    nets = {n for c in circuit["components"] for n in c["pins"].values()}
    if positive not in nets or negative not in nets:
        return {"status": "invalid_probe"}
    executable = find_ngspice() if executable is None else shutil.which(executable)
    if not executable:
        return {"status": "unavailable", "detail": "ngspice executable not found"}
    # SPICE identifiers are case-insensitive; opaque generated names preserve
    # distinct JSON nets (e.g. A and a) and avoid expression-reserved names.
    net_names = {n: f"n{i}" for i, n in enumerate(sorted(nets - {"0"}))}
    net_names["0"] = "0"
    positive, negative = net_names[positive], net_names[negative]
    lines = ["Lab mentor generated AC circuit"]
    for i, c in enumerate(circuit["components"]):
        p, kind = {pin: net_names[net] for pin, net in c["pins"].items()}, c["type"]
        if kind in {"R", "C"}:
            lines.append(f"{kind}{i} {p['1']} {p['2']} {c['value']:.12g}")
        elif kind == "V":
            lines.append(f"V{i} {p['+']} {p['-']} DC {c['dc']:.12g} AC {c['ac']:.12g}")
        else:
            # Explicitly an ideal small-signal VCVS; supply pins are checked
            # topologically but rail saturation is not modeled.
            lines.append(f"E{i} {p['out']} 0 {p['+']} {p['-']} {c['gain']:.12g}")
    voltage = lambda node: "0" if node == "0" else f"v({node})"
    lines += [".control", f"ac lin 1 {frequency:.12g} {frequency:.12g}",
              f"let reading = mag({voltage(positive)}-{voltage(negative)})",
              "wrdata reading.txt reading", "quit", ".endc", ".end"]
    try:
        with tempfile.TemporaryDirectory(prefix="lab-spice-") as folder:
            path = Path(folder)
            (path / "circuit.cir").write_text("\n".join(lines), encoding="ascii")
            run = subprocess.run([executable, "-n", "-b", "circuit.cir"], cwd=folder,
                                 capture_output=True, text=True, timeout=5,
                                 env={**os.environ, "SPICE_ASCIIRAWFILE": "1"})
            log = ((run.stdout or "") + (run.stderr or "")).lower()
            if any(marker in log for marker in ("singular matrix", "timestep too small", "fatal error")):
                return {"status":"failed", "detail":"Circuit has a solver/model degeneracy; check connectivity and sources"}
            output = path / "reading.txt"
            if run.returncode or not output.exists():
                return {"status": "failed", "detail": "Solver did not produce a reading"}
            rows = output.read_text().strip().splitlines()
            if len(rows) != 1 or len(rows[0].split()) != 2:
                return {"status": "failed", "detail": "Unexpected solver output shape"}
            observed_frequency, raw_value = map(float, rows[0].split())
            number(observed_frequency, "solver frequency", True)
            if abs(observed_frequency - frequency) > max(1e-9, frequency * 1e-5):
                return {"status": "failed", "detail": "Solver frequency does not match probe"}
            value = number(raw_value, "solver output")
            if value < 0:
                return {"status": "failed", "detail": "Solver returned negative magnitude"}
            return {"status": "ok", "value": value, "unit": "V",
                    "convention": "ac_magnitude", "model": "ideal_small_signal"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    except (OSError, ValueError, IndexError):
        return {"status": "failed", "detail": "Solver execution or output invalid"}
