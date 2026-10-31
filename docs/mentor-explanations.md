# ML 3 service and mentor explanation

The application backend has four distinct operations in `ML3Service`:

| Operation | Purpose |
| --- | --- |
| `retrieve_context` | Read this authenticated student's personal Meko memories and active instructor-approved equipment notes. |
| `explain_result` | Explain a supplied ML 2 diagnosis and its permitted next action. It retrieves authorized context itself. |
| `store_outcome` | Submit a session outcome through the durable duplicate guard. |
| `review_flag` | Route an instructor decision to the SQLite knowledge lifecycle. |
| `pending_reviews` | List the instructor's pending evidence-backed flags for their lab. |

`Principal` is a trusted backend authentication result. Never construct it from
a role or student ID sent by the Android app. The backend must also verify the
student's lab, session and equipment membership before calling these functions.
No HTTP routes or login service are implemented here.

## Explain an ML 2 result

ML 2 supplies `DiagnosticResult`: session ID, one of `wiring`, `concept`,
`apparatus`, or `undetermined`, the three ledger probabilities, `EvidenceItem`
records with IDs/source/verification status, explicit limitations, and exactly
one permitted next action. ML 3 does not recalculate the netlist, SPICE results,
probabilities, or next action. The response always includes those fields so the
app can show the evidence and uncertainty directly.

The template explanation works without any model. If Qwen is configured, its
short wording is an optional supplement in `optional_wording`. The authoritative
fields remain the template `explanation`, `next_action`, probabilities,
limitations and evidence IDs. The app should display these fields as the primary
guidance and should not treat optional model wording as a new decision or action.
The prompt tells Qwen to treat memories and evidence descriptions as data, to
avoid new calculations or actions, and to preserve ML 2's limits. A post-check
rejects wording that contains the safety terms, overconfident claims, or exceeds
600 characters. Personal memories stay in the app response and are not sent to
Qwen by default.
Model output is still untrusted prose and needs human review before relying on
it for safety critical guidance. Hard safety terms in ML 2 evidence/next action
trigger a refusal before the model is called.

Use `QwenTransport.from_env()` as the optional `generate` callable. Configure
`QWEN_BASE_URL`, `QWEN_MODEL`, and `DASHSCOPE_API_KEY` in the backend environment;
the URL and model depend on your Alibaba Model Studio workspace and region.
The transport calls the OpenAI-compatible `/chat/completions` endpoint. No Qwen
credential or live call is provided by the coding agent. See the [official API
reference](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope.md).

## Context layers and failure behavior

Personal Meko hits are labeled `source="personal_memory"` and
`verification="unverified"`, preserving each memory ID and available agent,
conversation, run and creation-time origin fields. Active knowledge notes
are labeled `source="approved_equipment_note"` and
`verification="instructor_verified"` with approver, approval time and evidence
IDs. They come only from `KnowledgeStore.active_notes` and are therefore filtered
for expiry, repair and simulation mode. A Meko failure produces
`memory_status="unavailable"`, while the current diagnostic result is still
returned and explained. No memory write occurs during explanation.

## Outcome write guard

`OutcomeWriter` uses a durable SQLite reservation keyed by authenticated student
ID and session ID. `ML3Service.store_outcome` uses it instead of calling
`MekoMemory.store_outcome` directly. An identical replay returns
`already_stored`; a changed payload for the same key is rejected. If the process
or Meko fails after reservation, the status becomes `needs_reconciliation` and
automatic retries stop. An operator must inspect the Meko result and authoritative
session record before deciding whether to retry or mark it complete. The exact
submitted outcome is kept in the local ledger and can be read with the
authenticated service's `local_outcome` operation while Meko is unavailable. SQLite
prevents concurrent backend workers sharing that file from both submitting the
same outcome; it does not make Meko itself transactional or guarantee that
semantic extraction preserved every field. Keep the exact session separately.

Use a durable server-owned path under ignored `data/` for the write ledger. Do
not delete or replace it on restart. Each synchronous worker needs its own
`OutcomeWriter` connection. The backend owns authentication, database backups,
and integration with Android and the instructor UI.

Run the offline explanation demo and tests:

```powershell
py -3 demo_mentor.py
py -3 -m unittest discover -s tests -v
```
