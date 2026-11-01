# ML1 shipping checks — 2026-11-01

Scope corrected after reading the shared/promoted build records: ML2 reasoning,
the existing backend and Android app are teammate-owned. The duplicate local API,
database, Docker and Android client added before that review were stopped,
backed up under ignored outputs and removed. Their generated credentials/state
are not included in the release. README and teammate branch files were not changed.

| Check | Actual result |
|---|---|
| ML1 unit/integration tests | 67 passed |
| Saved real session vs reviewed export | Exact reproduction, revision 45 |
| ML2 actual `internal_v1` parser at `02d4e36` | Passed for the reviewed v0.2 observation |
| Unsupported LED handling | Preserved as `LED`; no simulated behavior fabricated |
| Deployed `/health` | HTTP 200, `mode=stub` |
| Deployed OpenAPI | Existing multipart `/api/sessions`; no replacement contract |
| Deployed disposable synthetic upload | HTTP 200, `connection_ok`, ML1/ML2 `not_run` |
| ML1 upload library with same bytes | Provider-free manual draft with unknown pins |
| ML1 release scope | Library, reviewed examples, tests, docs and source photos |
| Credential check | Configured Gemini key absent from release files; .env excluded |

The existing backend owner still needs to call `labvision.upload.extract_upload`
from its upload flow, retain the draft/image for correction and send reviewed
observations through its existing ML2/ML3 pipeline. This is integration into
the deployed service, not a request to recreate that service or Android client.

Automatic vision remains experimental. This release does not claim a trained
detector, reliable automatic endpoint/pairing extraction, a corrected physical
circuit, new behavior models or completed production orchestration.

The reviewed real-photo graph has a supply-routing mismatch; preserve it as
observed data until its labels are checked. Do not use it as a correct reference.
