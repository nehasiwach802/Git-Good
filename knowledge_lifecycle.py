"""Persistent equipment review lifecycle. No Meko or other network calls."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3


def _time(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Use a timezone-aware timestamp supplied by the backend")
    return value.timestamp()


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")
    return value


@dataclass(frozen=True)
class Principal:
    """Trusted authentication result, never constructed from request role fields."""

    actor_id: str
    lab_id: str
    role: str

    def __post_init__(self):
        _text(self.actor_id, "actor_id")
        _text(self.lab_id, "lab_id")
        if self.role not in ("student", "instructor", "technician"):
            raise ValueError("Unknown role")


class KnowledgeStore:
    def __init__(self, path):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS equipment_reviews (
                flag_id TEXT PRIMARY KEY, lab_id TEXT NOT NULL,
                equipment_id TEXT NOT NULL, channel TEXT NOT NULL,
                simulated INTEGER NOT NULL, record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS equipment_repairs (
                lab_id TEXT NOT NULL, equipment_id TEXT NOT NULL,
                channel TEXT NOT NULL, simulated INTEGER NOT NULL,
                repaired_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_id TEXT NOT NULL, flag_id TEXT,
                action TEXT NOT NULL, actor_id TEXT NOT NULL,
                at TEXT NOT NULL, detail TEXT NOT NULL
            );
        """)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _write(self):
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def _audit(self, lab, flag_id, action, actor_id, now, detail):
        self._db.execute(
            "INSERT INTO knowledge_audit(lab_id,flag_id,action,actor_id,at,detail) VALUES(?,?,?,?,?,?)",
            (lab, flag_id, action, actor_id, now.isoformat(), json.dumps(detail)))

    def _save(self, record):
        self._db.execute("UPDATE equipment_reviews SET record=? WHERE flag_id=?",
                         (json.dumps(record, allow_nan=False), record["flag_id"]))

    def _load(self, flag_id):
        row = self._db.execute("SELECT record FROM equipment_reviews WHERE flag_id=?", (flag_id,)).fetchone()
        if row is None:
            raise ValueError("Review not found")
        return json.loads(row["record"])

    @staticmethod
    def _authorize(actor, lab, roles):
        if not isinstance(actor, Principal) or actor.lab_id != lab or actor.role not in roles:
            raise PermissionError("Actor is not authorized for this lab and action")

    def _repair_cutoff(self, flag):
        row = self._db.execute("""
            SELECT MAX(repaired_at) AS cutoff FROM equipment_repairs
            WHERE lab_id=? AND equipment_id=? AND simulated=? AND channel IN (?, '*')
        """, (flag["lab_id"], flag["equipment_id"], flag["simulated"], flag["channel"])).fetchone()
        return row["cutoff"]

    def enqueue(self, flag: dict, *, now: datetime) -> dict:
        """Trusted backend submits flag_equipment output; replay is idempotent."""
        _time(now)
        flag = json.loads(json.dumps(flag, allow_nan=False))
        for name in ("flag_id", "lab_id", "equipment_id", "channel", "metric", "reason"):
            _text(flag.get(name), name)
        if flag.get("status") != "pending_review" or type(flag.get("simulated")) is not bool:
            raise ValueError("Only unapproved flags with explicit simulated mode may be submitted")
        support = flag.get("supporting_sessions")
        if not isinstance(support, list) or not support:
            raise ValueError("Supporting sessions are required")
        observed = []
        for row in support:
            for name in ("session_id", "experiment_id", "evidence_id"):
                _text(row.get(name), name)
            timestamp = datetime.fromisoformat(row["observed_at"])
            if _time(timestamp) > _time(now):
                raise ValueError("Evidence cannot come from the future")
            observed.append(_time(timestamp))
        if _time(datetime.fromisoformat(flag["as_of"])) > _time(now):
            raise ValueError("Flag evaluation cannot come from the future")
        with self._write():
            existing = self._db.execute("SELECT record FROM equipment_reviews WHERE flag_id=?",
                                        (flag["flag_id"],)).fetchone()
            if existing:
                record = json.loads(existing["record"])
                original = {k: v for k, v in record["candidate"].items() if k != "as_of"}
                incoming = {k: v for k, v in flag.items() if k != "as_of"}
                if original != incoming:
                    raise ValueError("Conflicting flag ID; submit a distinct evidence revision")
                return record
            cutoff = self._repair_cutoff(flag)
            if cutoff is not None and any(at <= cutoff for at in observed):
                raise ValueError("Evidence predates equipment repair; aggregate only post-repair evidence")
            record = {"flag_id": flag["flag_id"], "status": "pending_review",
                      "candidate": flag, "submitted_at": now.isoformat(),
                      "review": None, "retirement": None}
            self._db.execute("INSERT INTO equipment_reviews VALUES(?,?,?,?,?,?)", (
                flag["flag_id"], flag["lab_id"], flag["equipment_id"], flag["channel"],
                flag["simulated"], json.dumps(record, allow_nan=False)))
            self._audit(flag["lab_id"], flag["flag_id"], "submitted", "backend", now, {})
            return record

    def review_queue(self, actor: Principal) -> list[dict]:
        self._authorize(actor, actor.lab_id, {"instructor"})
        rows = self._db.execute("SELECT record FROM equipment_reviews WHERE lab_id=? ORDER BY flag_id",
                                (actor.lab_id,)).fetchall()
        return [record for row in rows if (record := json.loads(row["record"]))["status"] == "pending_review"]

    def decide(self, actor: Principal, flag_id: str, *, approve: bool, note: str,
               now: datetime, expires_at: datetime | None = None) -> dict:
        _time(now)
        _text(note, "review note")
        if type(approve) is not bool:
            raise ValueError("approve must be boolean")
        if approve and (expires_at is None or _time(expires_at) <= _time(now)):
            raise ValueError("Approval requires an explicit future expiry")
        if not approve and expires_at is not None:
            raise ValueError("Rejected flags do not have an expiry")
        with self._write():
            record = self._load(flag_id)
            flag = record["candidate"]
            self._authorize(actor, flag["lab_id"], {"instructor"})
            if record["status"] != "pending_review":
                raise ValueError("Only pending flags can be reviewed")
            if _time(now) < _time(datetime.fromisoformat(record["submitted_at"])):
                raise ValueError("Review cannot precede submission")
            record["status"] = "approved" if approve else "rejected"
            record["review"] = {"actor_id": actor.actor_id, "at": now.isoformat(),
                                "note": note, "expires_at": expires_at.isoformat() if approve else None}
            self._save(record)
            self._audit(flag["lab_id"], flag_id, record["status"], actor.actor_id, now,
                        {"note": note, "expires_at": record["review"]["expires_at"]})
            return record

    def active_notes(self, lab_id: str, equipment_id: str, *, channel: str,
                     simulated: bool, now: datetime) -> list[dict]:
        """Student-safe equipment notes, filtered on every read; no scheduler needed."""
        _time(now)
        if type(simulated) is not bool:
            raise ValueError("simulated must be explicit")
        notes = []
        rows = self._db.execute("""SELECT record FROM equipment_reviews
            WHERE lab_id=? AND equipment_id=? AND channel=? AND simulated=? ORDER BY flag_id""",
            (lab_id, equipment_id, channel, simulated)).fetchall()
        for row in rows:
            record = json.loads(row["record"])
            review = record["review"]
            if record["status"] != "approved" or not review:
                continue
            if not _time(datetime.fromisoformat(review["at"])) <= _time(now) < _time(datetime.fromisoformat(review["expires_at"])):
                continue
            notes.append({"warning_id": record["flag_id"], "layer": "instructor_verified",
                          "equipment_id": equipment_id, "channel": channel,
                          "simulated": simulated, "note": review["note"],
                          "approved_by": review["actor_id"], "approved_at": review["at"],
                          "expires_at": review["expires_at"],
                          "supporting_evidence_ids": [r["evidence_id"] for r in record["candidate"]["supporting_sessions"]]})
        return notes

    def withdraw(self, actor: Principal, flag_id: str, *, note: str, now: datetime) -> dict:
        """Instructor retires incorrect or superseded evidence without a repair."""
        _time(now)
        _text(note, "withdrawal reason")
        with self._write():
            record = self._load(flag_id)
            self._authorize(actor, record["candidate"]["lab_id"], {"instructor"})
            if record["status"] not in ("pending_review", "approved"):
                raise ValueError("Only pending or approved records can be withdrawn")
            latest = record["review"]["at"] if record["review"] else record["submitted_at"]
            if _time(now) < _time(datetime.fromisoformat(latest)):
                raise ValueError("Withdrawal cannot precede the latest review event")
            record["status"] = "retired"
            record["retirement"] = {"actor_id": actor.actor_id, "at": now.isoformat(),
                                    "reason": "instructor_withdrawn", "note": note}
            self._save(record)
            self._audit(actor.lab_id, flag_id, "withdrawn", actor.actor_id, now, record["retirement"])
            return record

    def mark_repaired(self, actor: Principal, equipment_id: str, *, channel: str | None = None,
                      simulated: bool, note: str, now: datetime) -> int:
        self._authorize(actor, actor.lab_id, {"technician"})
        _time(now)
        _text(equipment_id, "equipment_id")
        _text(note, "repair note")
        if channel is not None:
            _text(channel, "channel")
        if type(simulated) is not bool:
            raise ValueError("simulated must be explicit")
        count = 0
        with self._write():
            rows = self._db.execute("""SELECT record FROM equipment_reviews
                WHERE lab_id=? AND equipment_id=? AND simulated=?""",
                (actor.lab_id, equipment_id, simulated)).fetchall()
            for row in rows:
                record = json.loads(row["record"])
                if channel is not None and record["candidate"]["channel"] != channel:
                    continue
                times = [record["submitted_at"]]
                if record["review"]:
                    times.append(record["review"]["at"])
                if any(_time(datetime.fromisoformat(at)) > _time(now) for at in times):
                    raise ValueError("Repair cannot precede an existing equipment event")
                if record["status"] not in ("pending_review", "approved"):
                    continue
                record["status"] = "retired"
                record["retirement"] = {"actor_id": actor.actor_id, "at": now.isoformat(),
                                        "reason": "equipment_repaired", "note": note}
                self._save(record)
                self._audit(actor.lab_id, record["flag_id"], "retired", actor.actor_id, now,
                            record["retirement"])
                count += 1
            self._db.execute("INSERT INTO equipment_repairs VALUES(?,?,?,?,?)",
                             (actor.lab_id, equipment_id, channel or "*", simulated, _time(now)))
            self._audit(actor.lab_id, None, "equipment_repaired", actor.actor_id, now,
                        {"equipment_id": equipment_id, "channel": channel, "simulated": simulated, "note": note})
        return count

    def history(self, actor: Principal, flag_id: str, *, now: datetime) -> dict:
        _time(now)
        record = self._load(flag_id)
        self._authorize(actor, record["candidate"]["lab_id"], {"instructor", "technician"})
        if record["status"] == "approved" and _time(datetime.fromisoformat(record["review"]["expires_at"])) <= _time(now):
            record["status"] = "expired"
        events = self._db.execute("""SELECT sequence,action,actor_id,at,detail
            FROM knowledge_audit WHERE flag_id=? ORDER BY sequence""", (flag_id,)).fetchall()
        record["events"] = [{**dict(row), "detail": json.loads(row["detail"])} for row in events]
        return record
