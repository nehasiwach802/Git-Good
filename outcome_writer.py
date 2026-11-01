"""Durable, at-most-once submission guard for semantic memory writes."""

from dataclasses import asdict
import hashlib
import json
import sqlite3

from lab_memory import SessionOutcome


class OutcomeWriter:
    """Use with trusted student identity and a durable backend-owned SQLite path.

    A crash after Meko accepts a write can leave status uncertain. This guard
    refuses automatic retries in that state rather than creating duplicates.
    """

    def __init__(self, path, memory):
        self._db = sqlite3.connect(path)
        self._db.execute("""CREATE TABLE IF NOT EXISTS outcome_submissions (
            student_id TEXT NOT NULL, session_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL,
            PRIMARY KEY(student_id,session_id))""")
        # Earlier local ledgers stored only a digest. Preserve their retry guard
        # and add exact local outcomes for all new submissions.
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(outcome_submissions)")}
        if "payload_json" not in columns:
            self._db.execute("ALTER TABLE outcome_submissions ADD COLUMN payload_json TEXT")
        self._db.commit()
        self._memory = memory

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def submit(self, student_id: str, outcome: SessionOutcome) -> dict:
        if not isinstance(student_id, str) or not student_id.strip():
            raise ValueError("Authenticated student ID is required")
        outcome = SessionOutcome(**asdict(outcome))
        payload = json.dumps(asdict(outcome), sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        # Reserve before the external write. Multiple workers sharing this DB
        # cannot call Meko twice for the same student/session.
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._db.execute("""SELECT payload_hash,status FROM outcome_submissions
                WHERE student_id=? AND session_id=?""", (student_id, outcome.session_id)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("Session outcome changed; reconcile the authoritative record first")
                return_value = {"status": "already_stored" if row[1] == "stored" else "needs_reconciliation"}
            else:
                self._db.execute("""INSERT INTO outcome_submissions
                    (student_id,session_id,payload_hash,payload_json,status) VALUES(?,?,?,?,?)""",
                    (student_id, outcome.session_id, digest, payload, "attempted"))
                return_value = None
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        if return_value is not None:
            return return_value
        # Any error leaves 'attempted'. An operator must determine whether Meko
        # accepted the write before manually resolving this status.
        self._memory.store_outcome(student_id, outcome)
        with self._db:
            self._db.execute("""UPDATE outcome_submissions SET status='stored'
                WHERE student_id=? AND session_id=? AND payload_hash=?""",
                (student_id, outcome.session_id, digest))
        return {"status": "stored"}

    def local_outcome(self, student_id: str, session_id: str) -> dict | None:
        """Read the exact reserved outcome for operator reconciliation."""
        row = self._db.execute("""SELECT payload_json,status FROM outcome_submissions
            WHERE student_id=? AND session_id=?""", (student_id, session_id)).fetchone()
        if row is None:
            return None
        return {"status": row[1], "outcome": json.loads(row[0]) if row[0] else None}
