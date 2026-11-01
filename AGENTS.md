## Meko team protocol

Build datapack: `gitgood-build`

- Before every task, recall the `gitgood-build` datapack.
- When a task ends, save a short summary to it.
- Promote every decision the others must follow (API contracts, schemas, datapack names, gotchas), and name which teammate made it.
- Never put keys or personal data in the build datapack.
- Never read or write the product's datapacks from the coding agent.

## Living project context

- At task start, read `context.md` and recall `gitgood-build`. Check the current repository before treating recalled context as current fact.
- When reviewing teammate work, inspect promoted/shared memories in the build datapack too; ordinary context search can omit promoted updates.
- At task end, update `context.md` when project state changes: implemented work, contract decisions and their owner, latest actual verification, blockers, and next steps. Then save a matching concise summary to `gitgood-build`, identifying `context.md` as the local context source.
- Promote new or changed decisions teammates must follow, with the decision owner's role. Do not promote proposals as agreed decisions or repeat unchanged decisions unnecessarily.
- Keep context summaries free of keys, personal data, raw student sessions, and product datapack contents. Link to repository contracts rather than duplicating their full schemas.
- If Meko is unavailable or a write fails, keep `context.md` current, record that synchronization is pending, and retry on the next task. Never claim a failed write synchronized successfully.
- This is an agent-maintained workflow, not a background file watcher. Updates happen during tasks; edits made outside an agent task are reconciled at the next task.
