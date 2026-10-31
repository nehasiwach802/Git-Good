"""Application-owner acceptance check. Never run this from the coding agent.

Requires two empty dedicated synthetic-data datapacks; does not create datapacks.
Only semantic memories are cleaned up. Provider conversation/search traces remain.
"""

import argparse
import os
import time
from uuid import UUID, uuid4

from lab_memory import MekoMemory, MemoryServiceError, SessionOutcome
from meko_transport import MekoTransport


def list_rows(memory, student, session):
    rows, page = [], 1
    while True:
        result = memory.view_context(student, session, page=page, page_size=100)
        rows.extend(result["memories"])
        if page >= result["total_pages"]:
            return rows
        page += 1


def wait_for(check, description, timeout, interval):
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if result:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MemoryServiceError(f"Timed out waiting for {description}")
        time.sleep(min(interval, remaining))


def memory_hits(result):
    hits = result.get("memory")
    if not isinstance(hits, list):
        raise MemoryServiceError("Unexpected personal recall response")
    return hits


def corrected_listing_ready(memory, session, memory_id, correction, observation):
    """Record structure-only diagnostics; never emit memory text or IDs."""
    rows = list_rows(memory, "a", session)
    target = next((row for row in rows if row.get("id") == memory_id), None)
    observation.clear()
    observation["row_count"] = len(rows)
    observation["target_present"] = target is not None
    if target is not None:
        for field in ("memory", "data", "text", "content"):
            observation[f"{field}_present"] = field in target
            observation[f"{field}_exact_match"] = target.get(field) == correction
    return target is not None and target.get("memory") == correction


def acceptance_check(memory, *, timeout=60, interval=3, report=print):
    """Run against configured scopes a/b. Tests may supply the offline fake."""
    if timeout <= 0 or interval <= 0:
        raise ValueError("Polling timeout and interval must be positive")
    session = "acceptance-" + uuid4().hex
    # Deliberately outside the cleanup block: never delete pre-existing memories.
    if list_rows(memory, "a", session) or list_rows(memory, "b", session):
        raise ValueError("Both acceptance datapacks must be empty; no outcome was submitted")
    if memory_hits(memory.recall("a", session, "Earlier RC filter checks")):
        raise ValueError("Acceptance scope has existing recall results; use a new empty scope")
    report("PASS: connection, personal listing, and initial recall")
    try:
        memory.store_outcome("a", SessionOutcome(
            session_id=session, experiment_id="simulated-rc-filter",
            equipment_id="simulated-scope", equipment_channel="CH2",
            connections_confirmed=True,
            measurements=({"node": "output", "value": 0.2, "unit": "V"},),
            diagnostic_evidence={"source": "simulated-ml2", "note":
                                 "The simulated RC output measured 0.2 V after checking wiring."},
            checks_performed=("Confirmed simulated RC filter wiring",),
            resolved=False, simulated=True))
        rows = wait_for(lambda: list_rows(memory, "a", session),
                        "extracted memories", timeout, interval)
        if any(not isinstance(row, dict) or not row.get("id") for row in rows):
            raise MemoryServiceError("Extracted memories lack IDs")
        ids = {row["id"] for row in rows}
        wait_for(lambda: any(hit.get("id") in ids for hit in memory_hits(
            memory.recall("a", session, "RC filter output 0.2 V after checking wiring"))),
            "recall of stored outcome", timeout, interval)
        report("PASS: simulated outcome submission, extraction, and recall")

        if list_rows(memory, "b", session) or memory_hits(memory.recall(
                "b", session, "RC filter output 0.2 V after checking wiring")):
            raise MemoryServiceError("Student isolation check failed")
        report("PASS: second student has no personal context from the first")

        memory_id = rows[0]["id"]
        correction = f"Simulated acceptance correction {session}: the RC output is 0.4 V."
        update_result = memory.correct_context("a", session, memory_id, correction)
        if update_result.get("success") is False:
            raise MemoryServiceError("Meko explicitly reported an unsuccessful correction")
        observation = {}
        try:
            wait_for(lambda: corrected_listing_ready(
                memory, session, memory_id, correction, observation),
                "corrected memory listing", timeout, interval)
        except MemoryServiceError:
            report("DIAGNOSTIC: correction listing " + ", ".join(
                f"{key}={value}" for key, value in observation.items()))
            report("DIAGNOSTIC: update response success flag present=" +
                   str("success" in update_result))
            raise
        wait_for(lambda: any(hit.get("id") == memory_id and hit.get("memory") == correction
                            for hit in memory_hits(memory.recall("a", session, correction))),
                 "corrected recall", timeout, interval)
        report("PASS: correction appears in listing and recall")

        memory.forget_context("a", session, memory_id)
        wait_for(lambda: not any(row.get("id") == memory_id
                                for row in list_rows(memory, "a", session)),
                 "deleted memory listing", timeout, interval)
        wait_for(lambda: not any(hit.get("id") == memory_id for hit in memory_hits(
            memory.recall("a", session, correction))), "deleted memory recall", timeout, interval)
        report("PASS: deleted memory absent from listing and recall")
    finally:
        # Empty scopes are required. Do not run concurrently with any application.
        # Never issue delete_all: enumerate only rows inside this dedicated test scope.
        try:
            for row in list_rows(memory, "a", session):
                memory.forget_context("a", session, row["id"])
            wait_for(lambda: not list_rows(memory, "a", session),
                     "test-memory cleanup", timeout, interval)
            report("PASS: synthetic semantic-memory cleanup (provider traces may remain)")
        except Exception:
            report("CLEANUP INCOMPLETE: inspect the dedicated synthetic scope in Meko")
            raise


def configured_memory():
    names = ("MEKO_BUILD_DATAPACK_ID", "MEKO_TEST_DATAPACK_A", "MEKO_TEST_DATAPACK_B")
    values = []
    for name in names:
        try:
            values.append(str(UUID(os.environ.get(name, ""))))
        except ValueError:
            raise ValueError(f"Set {name} to a valid datapack UUID") from None
    build, first, second = values
    # Also exclude the known repository build scope even if configuration is wrong.
    if "c3ea833a-a52a-49e5-9a78-23fc4276833e" in (first, second):
        raise ValueError("The repository build datapack cannot be an acceptance scope")
    return MekoMemory(MekoTransport.from_env(), {"a": first, "b": second}, build)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Enable actual Meko calls")
    parser.add_argument("--synthetic-datapacks", action="store_true",
                        help="Confirm both scopes are dedicated to this test and unused concurrently")
    args = parser.parse_args()
    if not args.live or not args.synthetic_datapacks:
        parser.error("Both --live and --synthetic-datapacks are required")
    try:
        acceptance_check(configured_memory())
    except (MemoryServiceError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print("ALL CHECKS PASSED for the configured synthetic scopes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
