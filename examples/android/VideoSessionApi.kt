package com.example.gitgood.integration

import com.google.gson.JsonObject
import java.io.File
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

// Reference for the existing SessionRepository, not a replacement Android app.
// Supply Firebase ID tokens from the SDK, never service-account credentials.
interface VideoSessionApi {
    @POST("api/v1/sessions")
    suspend fun create(@Header("Authorization") bearer: String,
        @Header("Idempotency-Key") requestId: String,
        @Body metadata: JsonObject): Response<JsonObject>

    // Field/route remain "image"; the actual file must be video/mp4.
    @Multipart @POST("api/v1/sessions/{id}/image")
    suspend fun upload(@Header("Authorization") bearer: String,
        @Header("Idempotency-Key") requestId: String, @Path("id") sessionId: String,
        @Part image: MultipartBody.Part,
        @Part("expected_session_version") version: RequestBody): Response<JsonObject>

    @GET("api/v1/sessions/{id}")
    suspend fun snapshot(@Header("Authorization") bearer: String,
        @Path("id") sessionId: String): Response<JsonObject>

    @GET("api/v1/sessions/{id}/image")
    suspend fun reviewImage(@Header("Authorization") bearer: String,
        @Path("id") sessionId: String): Response<ResponseBody>

    @POST("api/v1/sessions/{id}/events")
    suspend fun event(@Header("Authorization") bearer: String,
        @Path("id") sessionId: String, @Body event: JsonObject): Response<JsonObject>

    // Read-only native-frame pixel preview; does not consume an event UUID/version.
    @POST("api/v1/sessions/{id}/grid/suggest")
    suspend fun suggestHole(@Header("Authorization") bearer: String,
        @Path("id") sessionId: String, @Body request: GridSuggestionBody): Response<JsonObject>
}

data class GridSuggestionBody(
    val expected_session_version: Int,
    val candidate_revision: Int,
    val frame_id: String,
    val image_sha256: String,
    val board_fingerprint: String,
    val xy: List<Double>
)

// New mutations use sessionEvent() below and the same event endpoint:
// accept_grid, reject_grid, tap_endpoint, add_wire, remove_wire.
// Exact payloads/acknowledgements: docs/BACKEND_GRID_API.md.

fun mp4Part(file: File): MultipartBody.Part {
    require(file.isFile && file.length() in 1L..(50L * 1024 * 1024))
    return MultipartBody.Part.createFormData("image", "capture.mp4",
        file.asRequestBody("video/mp4".toMediaType()))
}

fun versionPart(version: Int): RequestBody =
    version.toString().toRequestBody("text/plain".toMediaType())

fun sessionEvent(type: String, eventId: String, version: Int, payload: JsonObject) =
    JsonObject().apply {
        addProperty("event_id", eventId)
        addProperty("expected_session_version", version)
        addProperty("type", type)
        add("payload", payload.deepCopy())
    }
