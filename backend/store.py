"""Single-instance durable SQLite store, atomic events and queued jobs.

Deploy DATA_DIR on a persistent disk. Connections belong to one call/thread.
Do not run this filesystem database across horizontally scaled containers.
"""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
import time
from uuid import uuid4


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':'))


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'sessions.sqlite3'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                request_hash TEXT NOT NULL, record TEXT NOT NULL, image BLOB NOT NULL,
                UNIQUE(owner,request_key));
            CREATE TABLE IF NOT EXISTS events (
                session_id TEXT NOT NULL,event_id TEXT NOT NULL,digest TEXT NOT NULL,
                response TEXT NOT NULL,PRIMARY KEY(session_id,event_id));
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,session_id TEXT NOT NULL,kind TEXT NOT NULL,
                state TEXT NOT NULL,started REAL,created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state,created);
            CREATE TABLE IF NOT EXISTS uploads (
                session_id TEXT NOT NULL,request_key TEXT NOT NULL,digest TEXT NOT NULL,
                response TEXT NOT NULL,PRIMARY KEY(session_id,request_key));
            CREATE TABLE IF NOT EXISTS session_media (
                session_id TEXT PRIMARY KEY,asset_id TEXT NOT NULL,receipt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS media_frames (
                session_id TEXT NOT NULL,frame_id TEXT NOT NULL,image BLOB NOT NULL,
                metadata TEXT NOT NULL,PRIMARY KEY(session_id,frame_id));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    @staticmethod
    def get(db, session_id, owner=None):
        row = db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        if row is None or owner is not None and row['owner'] != owner:
            return None
        return json.loads(row['record'])

    @staticmethod
    def save(db, record):
        db.execute('UPDATE sessions SET record=? WHERE id=?', (encode(record), record['session_id']))

    @staticmethod
    def enqueue(db, record, kind):
        job_id = str(uuid4())
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)', (job_id, record['session_id'], kind, 'queued', None, time.time()))
        record['job_id'] = job_id
        return job_id

    def claim(self):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET state='running',started=? WHERE id=?", (time.time(), row['id']))
            return dict(row)

    def recover(self):
        # Called on single-instance startup. Never automatically replay an
        # uncertain external model/memory operation after a process crash.
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM jobs WHERE state='running'").fetchall():
                record = self.get(db, row['session_id'])
                if record and record['job_id'] == row['id']:
                    record.update(state='failed', job_id=None, version=record['version'] + 1,
                                  error={'code':'interrupted_job','message':'Processing was interrupted; retry explicitly. Outcome writes may need reconciliation.'})
                    if row['kind']=='outcome':
                        record['ml3']['outcome_status']='needs_reconciliation'
                        record['state']='completed'
                    record['actions']=[] if row['kind']=='outcome' else [{'type':'retry_extraction'}]
                    self.save(db, record)
                db.execute("UPDATE jobs SET state='interrupted' WHERE id=?", (row['id'],))
