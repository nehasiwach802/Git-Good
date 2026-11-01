# Breadboard Wire Connections

Backend/ML2 owner: Tanu (implemented by Codex). Experiment ID
`wire-hole-practice-v1`, version `1`; analysis engine `wire_connections`.
Published through `GET /api/v1/experiments` and `GET /api/v1/capabilities`.

Use the existing JSON session creation, MP4 upload to
`POST /api/v1/sessions/{id}/image` with multipart field `image`, and nested events.
Enable `AUTO_GRID_ENABLED=true` for pixel-based entry. Review grid alignment and
printed labels, use `accept_grid`, `add_wire`/`tap_endpoint`/`remove_wire`, then
`confirm_candidate` with `reviewed_all_connections_and_board`. Poll for analysis
and close with `close_session`. See [BACKEND_GRID_API.md](BACKEND_GRID_API.md).
No endpoint, session-version field, or event-envelope changes.

Android must allow empty reported parts, reference components, reference ports,
and source ports for this engine. Skip component/source/measurement screens;
analysis declares `readings_required: false` and `power_required: false`.
The board profile covers central 30-row A–J strips without rails. Manual candidate
correction remains available if grid detection fails. Generic Gemini component
extraction is disabled for this mode; grid proposals and student wire entry remain.

The workflow is published for actual reviewed wire observations. The sample
expected pairs E5–F5, E12–F12, E20–F20 remain a **draft**: analysis lists observed
pairs without declaring them correct/incorrect. An instructor/backend owner must
verify desired pairs and set reference `approval: approved` to enable comparison.
The draft does not satisfy production approved-reference readiness checks.
References never enter vision and never create observed wires.

Approved comparison ignores wire names and endpoint direction, reports missing
and unexpected pairs, and distinguishes exact physical holes from board-strip
pair equivalence. Unknown/ambiguous endpoints and incomplete review block analysis.
Reviewed empty boards can report missing wires. No voltage, contact quality,
physical continuity or component behavior is inferred. ML3 uses its existing
schema2.0 diagnostic interface.

```powershell
.\.venv-backend\Scripts\python.exe -m unittest discover -s tests -p test_wire_workflow.py -v
.\.venv-backend\Scripts\python.exe tools/demo_backend.py --wire-only
```

The demo writes `outputs/backend/synthetic-wire-transcript.json` using a drawn
grid, synthetic MP4 and scripted student taps. It does not test real model accuracy.
Commit/push and redeploy to expose the catalog entry on Render. If
`EXPERIMENT_CATALOG_PATH` points to another catalog, add the record there too.
