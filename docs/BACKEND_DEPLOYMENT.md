# Deployment of the integrated backend

Use `Dockerfile.backend` on the existing backend branch. The image contains actual ML1/ML2/ML3 modules and ngspice. It starts a single uvicorn process and a durable background worker. Docker is not required for local checks.

The repository includes `render.yaml`, pinned direct runtime dependencies,
`.env.example`, an offline preflight command, container health checks, and a CI
container build/boot check. The startup script initializes the mounted directory's
ownership, then runs Python as `appuser`. No database files are deleted.

## Deploy this repository

1. Commit all backend changes and push `backend/android-connection-test`.
2. For the existing Render service, set Dockerfile path `Dockerfile.backend`,
   instance count 1, health path `/health`, shutdown delay 60 seconds, and attach
   a disk at `/app/data`. Alternatively apply `render.yaml` as a Blueprint after
   reviewing its settings. It targets service name `git-good-1`; change the name
   if it should create a separate service. The blueprint declares a paid starter
   service and 1 GB disk; applying it can incur hosting charges. No account
   resources are provisioned by editing this repository. Auto-deploy is off.
3. Set the three prompted values: `FIREBASE_PROJECT_ID`,
   `FIREBASE_SERVICE_ACCOUNT_JSON`, and `DEFAULT_LAB_ID`. Use the Firebase project
   already used by Android. Do not paste server credentials into chat or Git.
   Alternatively use Render's secret file named `firebase-service-account.json`,
   set `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-service-account.json`,
   and leave `FIREBASE_SERVICE_ACCOUNT_JSON` unset/blank. A nonblank JSON environment
   value takes precedence over the file, so remove stale values when switching.
4. Start with `VISION_ENABLED=false` and `QWEN_ENABLED=false` for manual review
   and template explanations. Enable them after adding the corresponding provider
   settings. Configure personal-memory mappings separately if memory is required.
5. Deploy, then check `/health`, `/ready`, and `/docs`. `/ready` checks storage,
   configured credentials, catalog, ngspice and enabled-provider settings; it does
   not call providers. A process can be healthy while `/ready` reports missing
   configuration. Supply approved catalog records before real lab use.

Persistent disks require paid Render services; the disk and Blueprint settings
follow [Render disk documentation](https://render.com/docs/disks) and the
[Blueprint specification](https://render.com/docs/blueprint-spec).

Offline configuration check (prints check names/booleans, no secret values):

```powershell
python -m backend.preflight
python -m backend.preflight --production
```

The production check additionally requires at least one approved, non-simulated
experiment. The bundled synthetic examples intentionally fail that check.
Neither command requests model inference or reads/writes a product datapack.
For local `.env` usage, explicitly load it with
`python -m uvicorn backend.app:app --env-file .env`; the deployment host injects
environment settings directly.

## Diagnose Firebase authentication

`/ready` now parses the selected service-account JSON, requires
`type=service_account`, checks its `project_id` against `FIREBASE_PROJECT_ID`,
and loads its private key with Firebase Admin. A nonempty variable or an existing
file alone no longer passes. Unsupported ambient/user ADC credentials are not
accepted by this service-account deployment path. Errors expose only safe codes
such as `missing_credentials`, `unreadable_credentials`, `invalid_credentials_json`,
`not_service_account`, `project_mismatch` or `invalid_service_account`.

Offline validation cannot prove the key is active or that its service account
has IAM permission. `/ready` explicitly reports `firebase_permissions_verified=false`.
Run this separate diagnostic in the deployment host's Shell after setting its
secrets (it contacts Google; never run it as a public HTTP health check):

```sh
python -m backend.firebase_diagnostic --live
```

It separately checks credential loading, OAuth token refresh, then Firebase Auth
user-read access. By default it looks up a random synthetic UID: an authorized
`UserNotFoundError` response counts as a successful permission check. Optionally
pass `--uid` for a designated test user. It never prints the credential, access
token, UID or returned user record. Output identifies failed stages and exception
types; provider messages are suppressed. CLI exits nonzero on failure.

Authentication requests keep `check_revoked=True`. Invalid/expired/revoked tokens,
disabled/deleted users and tenant mismatches return 401. Service credential errors,
OAuth refresh/IAM failures and Firebase availability failures return 503. Unexpected
backend errors return 500. Server logs contain only stage/exception type, never
raw token/key contents or exception messages. Investigate the exception type in
Render logs instead of assuming every failure means the Android token is invalid.

For credential replacement, use the complete newly downloaded JSON and ensure
both its project_id and FIREBASE_PROJECT_ID match the intended Android project.
Have the account administrator revoke any actually exposed old key. Replace the
host secret, redeploy (the Admin app caches credentials), then run the live
diagnostic and an authenticated Android request. The coding agent has not verified
the deployed account/key or revoked any keys.

Vision is independent of Firebase authentication. Manual mode can stay
`VISION_ENABLED=false`; for actual image extraction set `GEMINI_API_KEY` and an
available image-capable `GEMINI_MODEL`, then set `VISION_ENABLED=true` and redeploy.
Enabling vision alone cannot repair a Firebase 401.

## Required deployment configuration

- Persistent writable disk mounted at `/app/data`; set `DATA_DIR=/app/data`. Sessions/images, job queue, equipment knowledge and outcome ledger are SQLite files there. An ephemeral filesystem loses this data on redeploy. Use one instance and one worker; horizontal scaling needs a shared database/job queue/object store redesign.
- `FIREBASE_PROJECT_ID`: Android's Firebase project. Supply server credentials via the host's secret configuration using `FIREBASE_SERVICE_ACCOUNT_JSON`, or a secret credential file with `GOOGLE_APPLICATION_CREDENTIALS`. Never commit credentials or put them in Android. Set `DEFAULT_LAB_ID` deliberately; instructor roles/lab claims must be provisioned server-side.
- An approved experiment catalog via `EXPERIMENT_CATALOG_PATH`, or replace `backend/catalog.json` with reviewed records. The bundled two records are synthetic development examples with `workflow_approved=false`; they do not establish a real five-experiment lab catalog. Each record needs a validated ML2 reference, known board geometry, reported part types, correspondence configuration, source-port bindings where needed, and explicit workflow/simulation flags. See `backend/catalog.json`. Approve only actually supported models/analyses and instructor-defined checks; LED detection does not imply an LED electrical model.

Optional provider configuration:

- ML1: `GEMINI_API_KEY`, `GEMINI_MODEL`; set `VISION_ENABLED=false` for honest manual-entry mode. Missing/failed vision returns unknown endpoints for manual correction. No trained detector or live image accuracy has been validated by this integration.
- ML3 memory: `MEKO_MCP_URL`, `MEKO_API_TOKEN`, `MEMORY_SCOPES_FILE` pointing to an operator-owned JSON object mapping Firebase UIDs to isolated personal datapacks. Provision those outside the coding agent. Never map any student to `gitgood-build`; the adapter rejects it. Do not place this mapping in source control or the Docker build context.
- Qwen: `QWEN_MODEL`, `QWEN_BASE_URL`, `DASHSCOPE_API_KEY`. If omitted, grounded template explanations work. A configured model adds optional wording; it does not decide circuit facts or probabilities.

Start locally after setting server credentials:

```powershell
python -m pip install -e ".[backend,test]"
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
```

For Render select the backend branch, Docker runtime, Dockerfile path `Dockerfile.backend`, health path `/health`, configure the persistent disk and secrets, then redeploy. The container honors `$PORT`. Selecting or buying hosting resources remains an account-owner action; this repository change does not provision a disk or change the live service.

After deployment check `/health` reports `mode=integrated`, `/ready` returns 200, and `/docs` shows `/api/v1/sessions`. Then create an authenticated JSON session from Android, upload a synthetic image separately, poll, review/correct, submit readings, close_session, and verify ownership with another test account. Test live vision accuracy and memory behavior with approved test accounts separately. This coding session does not access product datapacks or claim live provider acceptance.

Do not label software test success as real-photo/model accuracy. Production acceptance additionally needs the approved experiments, auth claims/credentials, configured disk, provider test accounts, retention policy and a real-device Android test. The existing public URL serves whatever commit its hosting configuration deploys; local edits are not live until committed/pushed and redeployed.
