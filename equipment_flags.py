"""Deterministic cross-session equipment evidence aggregation, with no I/O."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
from typing import Iterable

from lab_memory import SessionOutcome


# Units are deliberately constrained. RMS/peak/peak-to-peak belong in metric,
# not in an inferred conversion that could silently compare unlike quantities.
UNIT_SCALES = {"V": ("V", 1.0), "mV": ("V", 0.001),
               "A": ("A", 1.0), "mA": ("A", 0.001),
               "Hz": ("Hz", 1.0), "kHz": ("Hz", 1000.0)}


@dataclass(frozen=True)
class EquipmentEvidence:
    evidence_id: str
    lab_id: str
    student_id: str
    session_id: str
    experiment_id: str
    equipment_id: str
    channel: str
    metric: str
    expected: float
    observed: float
    tolerance: float
    unit: str
    observed_at: datetime
    connections_confirmed: bool
    netlist_matches_reference: bool
    simulated: bool

    def __post_init__(self):
        for name in ("evidence_id", "lab_id", "student_id", "session_id", "experiment_id",
                     "equipment_id", "channel", "metric"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a nonempty canonical identifier")
        for name in ("expected", "observed", "tolerance"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite and numeric")
        if self.tolerance <= 0:
            raise ValueError("tolerance must be a positive absolute tolerance")
        if self.unit not in UNIT_SCALES:
            raise ValueError("Unsupported unit; normalize it in the trusted backend")
        if not isinstance(self.observed_at, datetime) or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        for name in ("connections_confirmed", "netlist_matches_reference", "simulated"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if not math.isfinite(self.relative_error):
            raise ValueError("Normalized discrepancy must be finite")

    @property
    def relative_error(self):
        return (self.observed - self.expected) / max(abs(self.expected), self.tolerance)

    @classmethod
    def from_outcome(cls, outcome: SessionOutcome, *, evidence_id: str, lab_id: str,
                     student_id: str, measurement_index: int, expected: float,
                     tolerance: float, metric: str, observed_at: datetime,
                     netlist_matches_reference: bool):
        """Bridge to responsibility 1; predictions/reference match come from ML 2."""
        outcome = SessionOutcome(**asdict(outcome))
        if type(measurement_index) is not int or not 0 <= measurement_index < len(outcome.measurements):
            raise ValueError("measurement_index must select an existing measurement")
        reading = outcome.measurements[measurement_index]
        return cls(evidence_id, lab_id, student_id, outcome.session_id, outcome.experiment_id,
                   outcome.equipment_id, outcome.equipment_channel, metric, expected,
                   reading["value"], tolerance, reading["unit"], observed_at,
                   outcome.connections_confirmed, netlist_matches_reference, outcome.simulated)


@dataclass(frozen=True)
class FlagPolicy:
    min_sessions: int = 3
    min_students: int = 3
    min_experiments: int = 2
    max_error_spread: float = 0.15
    lookback_days: int = 7

    def __post_init__(self):
        for name in ("min_sessions", "min_students", "min_experiments"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 2:
                raise ValueError(f"{name} must be an integer of at least two")
        if type(self.lookback_days) is not int or self.lookback_days < 1:
            raise ValueError("lookback_days must be a positive integer")
        if type(self.max_error_spread) not in (int, float) or not math.isfinite(self.max_error_spread) or self.max_error_spread < 0:
            raise ValueError("max_error_spread must be finite and nonnegative")


def flag_equipment(evidence: Iterable[EquipmentEvidence], *, as_of: datetime,
                   policy: FlagPolicy = FlagPolicy()) -> list[dict]:
    """Return unapproved review candidates; the caller owns evidence persistence.

    Input is a trusted backend snapshot. IDs are scoped to the lab. Replayed
    observations do not increase support; conflicting reuse of an ID is rejected.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    unique = {}
    sessions = {}
    for row in evidence:
        if not isinstance(row, EquipmentEvidence):
            raise ValueError("All observations must be EquipmentEvidence")
        key = (row.lab_id, row.evidence_id)
        if key in unique and unique[key] != row:
            raise ValueError("Conflicting evidence_id; replace the authoritative record first")
        unique[key] = row
        session_key = (row.lab_id, row.student_id, row.session_id)
        if session_key in sessions and sessions[session_key] != row.experiment_id:
            raise ValueError("A session cannot refer to different experiments")
        sessions[session_key] = row.experiment_id

    groups = defaultdict(list)
    cutoff = as_of - timedelta(days=policy.lookback_days)
    for row in unique.values():
        if not cutoff <= row.observed_at <= as_of:
            continue
        if not row.connections_confirmed or not row.netlist_matches_reference:
            continue
        if abs(row.observed - row.expected) <= row.tolerance:
            continue
        base_unit, _ = UNIT_SCALES[row.unit]
        direction = "low" if row.relative_error < 0 else "high"
        signature = (row.lab_id, row.equipment_id, row.channel, row.metric,
                     base_unit, direction, row.simulated)
        groups[signature].append(row)

    flags = []
    for signature, rows in sorted(groups.items()):
        rows.sort(key=lambda row: (row.relative_error, row.evidence_id))
        candidates = {}
        for start in range(len(rows)):
            # Complete-link windows prevent a chain of dissimilar errors from
            # looking like one repeated anomaly. Keep one observation per session.
            window = [row for row in rows[start:] if
                      row.relative_error - rows[start].relative_error <= policy.max_error_spread + 1e-12]
            per_session = {}
            for row in sorted(window, key=lambda row: row.evidence_id):
                per_session.setdefault((row.student_id, row.session_id), row)
            support = list(per_session.values())
            if (len(support) < policy.min_sessions or
                len({row.student_id for row in support}) < policy.min_students or
                len({row.experiment_id for row in support}) < policy.min_experiments):
                continue
            session_keys = frozenset(per_session)
            previous = candidates.get(session_keys)
            if previous is None or sorted(row.evidence_id for row in support) < sorted(row.evidence_id for row in previous):
                candidates[session_keys] = support
        for session_keys, support in sorted(candidates.items(), key=lambda item: sorted(item[0])):
            if any(session_keys < other for other in candidates):
                continue
            lab, equipment, channel, metric, unit, direction, simulated = signature
            identity = json.dumps([signature, sorted(row.evidence_id for row in support)], separators=(",", ":"))
            errors = [row.relative_error for row in support]
            flags.append({
                "flag_id": "equipment-" + hashlib.sha256(identity.encode()).hexdigest()[:24],
                "status": "pending_review", "suspected_cause": "apparatus",
                "lab_id": lab, "equipment_id": equipment, "channel": channel,
                "metric": metric, "unit": unit, "anomaly": direction,
                "simulated": simulated, "session_count": len(support),
                "student_count": len({row.student_id for row in support}),
                "experiment_ids": sorted({row.experiment_id for row in support}),
                "relative_error_range": [min(errors), max(errors)],
                "reason": "Similar out-of-tolerance readings across students and experiments on confirmed reference-matching circuits. Instructor review required.",
                "policy": asdict(policy), "as_of": as_of.isoformat(),
                "supporting_sessions": [{
                    "session_id": row.session_id, "experiment_id": row.experiment_id,
                    "evidence_id": row.evidence_id, "expected": row.expected,
                    "observed": row.observed, "tolerance": row.tolerance,
                    "unit": row.unit, "observed_at": row.observed_at.isoformat(),
                } for row in sorted(support, key=lambda row: row.evidence_id)],
            })
    return sorted(flags, key=lambda flag: flag["flag_id"])
