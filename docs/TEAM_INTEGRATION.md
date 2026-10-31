# ML1 into the existing team implementation

This supersedes local notes that assumed the team backend and ML2 adapters were
not implemented. ML1 supplies library functions and observation fixtures, not a
replacement HTTP service, Android client or reasoning engine.

## Existing contracts

- Backend URL: https://git-good-1.onrender.com/. Live `/health` returns
  `status=ok`, `mode=stub`, `service=android-connection-test`. Published routes
  are `/health` and POST `/api/sessions`. Upload remains multipart fields
  `experiment_id`, `description`, `image` (JPEG/PNG, 5 MiB / 20 MP).
  The current response marks ML1/ML2 `not_run`. A receipt is not a diagnosis
  or stored session. Existing source: `origin/backend/android-connection-test`,
  `backend/app.py`, `docs/ANDROID_CONNECTION_TEST.md`.
- ML2: `origin/tanu` already implements generalized contract 2.0, `ml1_v0.1`
  and `internal_v1` adapters, capability checks, ngspice and isolated 7400
  analysis. Keep its `docs/GENERALIZED_CORE.md`, `docs/contract.md` and ownership.
- ML3: shared promoted records describe the existing memory adapter and MCP
  transport. Backend identity, personal-datapack mapping and authoritative
  persistence stay with their owners. ML1 does not access product datapacks.
- Android: use the existing app, Retrofit upload contract and deployed URL.
  No new Android client is included in ML1's work.

Sources: shared/promoted `gitgood-build` records, current remote branch source,
and the actual deployed health/OpenAPI response. The older record saying public
hosting was pending is superseded by the reachable deployment.

## Existing backend calls ML1

```python
from labvision.upload import extract_upload

ml1_result = extract_upload(
    image_bytes, physical_board_profile,
    known_parts=["7400", "led"], try_vision=True, timeout=20,
)
```

The backend owner can put this result in the existing `ml1` response field;
the Android multipart request does not change. Run this synchronous operation
in a worker thread from an async route. Board geometry and reported parts come
from trusted experiment configuration. Never pass reference wiring to extraction.

Result fields: `mode`, `status`, image-bound `candidate`, `board`, `image`,
`unknown_endpoints`, `error_code`, `message`, and `netlist: null`. Modes are
`gemini`, `manual`, `manual_fallback`. Provider failure yields a genuinely partial
manual-entry draft, not fake model success. `try_vision=False` makes no provider
request. Model confirmation flags are reset; keys/raw provider errors aren't returned.

This function creates no HTTP route or persistent session and calls no ML2/ML3.
Temporary upload files are removed on return. The backend retains the image
when later correction requires it. All image coordinates are native file pixels;
EXIF rotation is not silently applied.

## Existing ML2 adapters receive ML1

```python
from labvision.handoff import reasoning_input

input_spec = reasoning_input(candidate, board)
# Existing ML2 generalized request: request["input"] = input_spec.
# Trusted backend independently supplies approved reference, explicit identity/
# port correspondence, analysis configuration and measurements.
```

- v0.1 delegates to the existing `ml1_v0.1` adapter, including partial evidence.
- Fully reviewed v0.2 exports the existing `internal_v1` observation format so
  external terminals are retained. Partial v0.2 is explicitly blocked until
  resolved/reviewed. It is not silently interpreted as the older hole format.
- No component is dropped, reference connection substituted or supply voltage
  inferred. Node IDs remain revision-local. Review does not imply correctness.
- `LED` is preserved even though ML2's current model registry lacks LED behavior;
  its engine must report the capability gap, not simulate a different circuit.

`examples/integration/reviewed-v02/` contains reviewed candidate, board, netlist
and `reasoning-input.json`. This is an observed circuit with a documented supply
routing mismatch, not a known-correct reference. Conversion passed the actual
ML2 `ADAPTERS["internal_v1"]` and `validate_observation` at commit `02d4e36`,
without changing or vendoring ML2 source.

## Export and check

```powershell
python tools/export_ml1_handoff.py "ckt breadboard/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).jpeg" --session "examples/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).annotations.json" --netlist "examples/WhatsApp Image 2026-10-31 at 8.23.36 PM (1).netlist.json" --out outputs/new-ml1-handoff
python -m unittest discover -s tests -q
```

Saved annotations must reproduce the reviewed export exactly; changed revisions,
pixels, pairing or topology cannot inherit old review. Source files aren't overwritten.

Actual verification: 67 ML1 tests pass; reviewed v0.2 passes the teammate's
observation parser. Automatic extraction remains experimental (local baseline
2/7 central wire ends; Gemini image requests timed out). The demonstrated path
is calibration, explicit review/correction and deterministic connectivity export.
See `reports/VISION_BASELINE.md` and `reports/FIRST_REAL_NETLIST_REVIEW.md`.

A disposable synthetic PNG uploaded to the existing public `/api/sessions`
returned HTTP 200 `connection_ok`. The live receipt still explicitly reported
both models `not_run`. Local `extract_upload` processed those same bytes in
provider-free mode and returned the expected manual draft. This verifies
transport and the ML1 call boundary, not that the deployed route invokes ML1.
