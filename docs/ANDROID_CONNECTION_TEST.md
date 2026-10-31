# Android upload connection test

Historical connectivity endpoint only. The integrated application now uses
[API 1.0](BACKEND_API.md) and [deployment configuration](BACKEND_DEPLOYMENT.md).
The previously verified public smoke deployment is not proof that these new
working-tree changes have been deployed.

## Verified public service

Base URL: https://git-good-1.onrender.com/

- GET https://git-good-1.onrender.com/health
- POST https://git-good-1.onrender.com/api/sessions
- API documentation: https://git-good-1.onrender.com/docs

Verified on 2026-11-01: health and OpenAPI retrieval succeeded; actual multipart
upload of examples/connection-test.png returned HTTP 200, connection_ok, stub
mode, 77 bytes and the matching image SHA-256. Android-to-service testing still
needs to be performed on the phone; this verification was a remote HTTP client.
The service does not run ML1/ML2 or retain a session.

Branch: backend/android-connection-test. ML1 and ML2 are explicit stubs; ML3,
Gemini, Qwen, Meko and ngspice are not called. This is a request/response smoke
test, not a persistent chatbot/session service. The /api/sessions path reserves
the future API shape, but the returned request_id is only a receipt: there is
no stored session or GET-session endpoint yet. Uploaded images are discarded.

## Public deployment

Deploy this branch on a container host with HTTPS and use Dockerfile.backend.
Configure the host's Dockerfile path to Dockerfile.backend, expose its PORT
(default 8000), and set the health check to /health. No model keys or database
are required. The user deployed the public service listed above; the coding agent
verified its health and upload endpoint. These instructions also cover redeployment.

The host will provide https://YOUR-SERVICE.example. Give that URL to Android;
use a trailing slash for Retrofit's baseUrl. GET /health should return mode=stub.
Interactive API documentation is available at /docs and OpenAPI at /openapi.json.

This test is unauthenticated and retains no uploaded image. Configure the host's
request-body limit to 6 MiB and request timeout to 30 seconds to bound multipart
parsing before application validation. Restrict access/rate-limit the temporary
service at the host if needed. Authentication and durable session handling belong
to the next backend stage, not this connection example. Do not use real student
data in the public smoke test.

## Contract

POST /api/sessions using multipart/form-data:

| Field | Type | Rules |
|---|---|---|
| experiment_id | text | 1..100 letters/digits/underscore/hyphen |
| description | text | 1..2000 characters; not whitespace-only |
| image | file | Valid JPEG/PNG, at most 5 MiB and 20 megapixels |

Any validly formatted experiment ID is accepted in stub mode. No experiment
catalog or actual LED analysis is loaded. Success is HTTP 200 with status
connection_ok, mode=stub, request_id, echoed text, image size/dimensions/SHA-256,
message and ml1/ml2 objects explicitly marked not_run. Invalid form inputs return
422; unsupported/corrupt image or mismatched MIME type 415; oversized image 413.
Error responses can contain either error/fields or FastAPI detail; Android should
handle non-2xx status first and show a generic upload error for unknown formats.

## Android (Retrofit)

```kotlin
interface BackendApi {
    @Multipart
    @POST("api/sessions")
    suspend fun upload(
        @Part("experiment_id") experimentId: RequestBody,
        @Part("description") description: RequestBody,
        @Part image: MultipartBody.Part
    ): UploadReceipt
}
```

Create the file part with MultipartBody.Part.createFormData("image", filename,
imageBody). Read the selected Android content URI through ContentResolver; a
phone-local path is not accessible to the server. Set the file body's media type
to image/jpeg or image/png matching the actual image. Do not manually set the
request Content-Type header: Retrofit/OkHttp generates the multipart boundary.
Render response.message and response.status for the smoke test. Android native
HTTP does not require browser CORS configuration. Include INTERNET permission.

Example response fields Android can initially deserialize:

```kotlin
data class UploadReceipt(
    val request_id: String,
    val mode: String,
    val status: String,
    val experiment_id: String,
    val description: String,
    val message: String
)
```

## Send a request to the deployed URL

PowerShell (curl.exe avoids the PowerShell curl alias):

```powershell
curl.exe -X POST "https://YOUR-SERVICE.example/api/sessions" `
  -F "experiment_id=led-circuit-001" `
  -F "description=My LED is not glowing" `
  -F "image=@examples/connection-test.png;type=image/png"
```

Use the included synthetic PNG or a disposable circuit photo. Seeing connection_ok
and the correct size/hash confirms that the backend received image bytes rather
than just a filename. It does not verify model or diagnosis correctness.

## Development verification

```powershell
python -m pip install -e ".[backend,test]"
python -m unittest discover -s tests -p test_backend.py -v
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

For the isolated environment created during implementation, use
.venv-backend/Scripts/python.exe instead of python. The public Android test uses
the deployed HTTPS URL, not this development command or a laptop address.
