# Responsibility 3: equipment knowledge lifecycle

`knowledge_lifecycle.py` accepts responsibility-2 flags into a persistent SQLite
review queue. It supports instructor approval/rejection, approval provenance and
expiry, student-visible active warnings, technician repair retirement, and an
audit history. It uses Python's standard library and makes no network calls.

## Try the complete simulated flow

```powershell
py -3 demo_knowledge.py
py -3 -m unittest discover -s tests -v
```

The demo uses a temporary database and simulated identities. It prints one queued
flag despite a replay, zero warnings before approval, one warning after approval
and reopening the database, zero at expiry, and zero after repair. It also prints
approval provenance and audit actions. Nothing is written to Meko.

## Backend contract

Create `KnowledgeStore(path)` using a durable server-owned path, such as
`data/knowledge.sqlite3` (create the parent directory first). The root `data/`
folder is ignored by Git. Close the store or use it as a context manager. Use one
store/connection per synchronous worker; do not share a connection across threads.
SQLite transactions make review/repair changes atomic. This is a local v1 schema;
future incompatible schema changes need an explicit migration.

- `enqueue(flag, now=...)`: submit trusted `flag_equipment` output. Stores the
  complete supporting evidence snapshot. Same-ID replay returns the existing
  record without resetting review/retirement or adding another audit event.
  Same-ID conflicting payloads are rejected; a changed `as_of` alone is ignored.
- `review_queue(principal)`: instructors list pending records in their own lab.
- `decide(principal, flag_id, approve=..., note=..., now=..., expires_at=...)`:
  only instructors can review pending records. Approval requires explicit future
  expiry and an instructor-authored warning note. Rejection requires a reason and
  remains hidden. Reviewed records cannot be silently approved or edited again.
- `active_notes(lab_id, equipment_id, channel=..., simulated=..., now=...)`:
  return only approved, unexpired, unretired notes for the exact equipment channel
  and mode. This is what the backend serves when the next student opens a lab.
  Pending claims and rejected records never appear. Expiry is checked on every
  read, including the exact expiry boundary; no background scheduler is required.
- `mark_repaired(technician, equipment_id, channel=..., simulated=..., note=..., now=...)`:
  retire matching pending and approved records and record the repair. `channel=None`
  repairs all channels on that equipment. Other labs/equipment/modes are unaffected.
  A candidate containing any evidence observed at or before the last applicable
  repair is rejected; reaggregate only post-repair observations for new incidents.
- `history(principal, flag_id, now=...)`: instructors/technicians in the same lab
  can inspect original evidence, review, retirement, and ordered audit events.
  An approval past its expiry is shown as `expired` on read; its stored approval
  and expiry remain intact as provenance.
- `withdraw(instructor, flag_id, note=..., now=...)`: retire an incorrect or
  superseded pending/approved record with an explanation, without claiming a
  technician repair. Use this before replacing evidence that supported approval.

`Principal(actor_id, lab_id, role)` must come from real backend authentication and
role lookup. Never trust a student request to claim `role="instructor"`. The
library checks the supplied principal but does not implement login or HTTP routes.
`enqueue` is an internal service operation, not a student-facing upload endpoint.
Supply server-derived aware timestamps, not arbitrary client clocks.

## What approved students receive

Each active note includes a warning ID, `layer="instructor_verified"`, equipment,
channel, simulated label, instructor-authored note, approval identity/time, expiry,
and supporting evidence IDs. Exact measurements remain in the review history;
evidence-link endpoints must enforce backend access control. Equipment approval
is a reviewed warning, not a claim that the system proved an apparatus fault.

This SQLite record is the authority for warning visibility. Semantic memory
promotion is not used as an expiry/retirement mechanism: a stale retrieved note
must never bypass `active_notes`. No product Meko datapacks are touched by this
module or by the coding agent. If the application later mirrors approved notes
to Meko, it must validate every returned warning ID against this lifecycle store
and implement synchronization/deletion separately. That mirroring is not built here.

## Remaining integration and defaults

The module completes the local lifecycle behavior, not the shared instructor web
view, Android UI, authentication service, or application deployment. Instructor
chooses expiry explicitly; no implicit validity period is invented. Review
revisions get distinct flag IDs; consolidating related revisions into one incident
and evidence-correction invalidation still require backend policy. Until then,
do not remove/replace authoritative evidence supporting an approved note without
retiring that note through an authorized workflow. Database administrators can
alter SQLite, so the application audit is persistent but not tamper-proof.
