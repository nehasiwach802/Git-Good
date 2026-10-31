"""Offline, simulated equipment flag demonstration; no Meko calls."""

from datetime import datetime, timezone
import json

from equipment_flags import EquipmentEvidence, flag_equipment


def main():
    now = datetime.now(timezone.utc)
    rows = [EquipmentEvidence(
        evidence_id=f"sim-reading-{index}", lab_id="demo-lab", student_id=f"sim-student-{index}",
        session_id=f"sim-session-{index}", experiment_id=experiment,
        equipment_id="scope-3", channel="CH2", metric="voltage_amplitude_peak",
        expected=expected, observed=expected * 0.5, tolerance=expected * 0.05,
        unit="V", observed_at=now, connections_confirmed=True,
        netlist_matches_reference=True, simulated=True,
    ) for index, (experiment, expected) in enumerate(
        [("rc-filter", 1.0), ("inverting-amplifier", 2.0), ("rc-filter", 1.5)], start=1)]
    print("SIMULATED DEMO - no real equipment diagnosis or shared warning")
    print("After two students:", flag_equipment(rows[:2], as_of=now))
    flags = flag_equipment(rows, as_of=now)
    print("After three students:")
    print(json.dumps(flags, indent=2))
    print("Replaying a session keeps count:",
          flag_equipment([*rows, rows[0]], as_of=now)[0]["session_count"])


if __name__ == "__main__":
    main()
