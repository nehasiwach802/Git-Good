package com.example.gitgood.data.backend

import kotlinx.serialization.encodeToString
import java.io.File
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** Production API v1.1. The older FakeSessionRepository remains demo-only. */
@Singleton
class LiveSessionRepository @Inject constructor(private val http: BackendHttpClient) : SessionApi {
    override suspend fun experiments(): List<BackendExperiment> =
        http.json.decodeFromString<Catalog>(http.request("GET", "/api/v1/experiments")).experiments

    override suspend fun create(request: CreateSession, key: String): BackendSession =
        decode(http.request("POST", "/api/v1/sessions", http.json.encodeToString(request).toByteArray(), idempotencyKey = key))

    override suspend fun get(id: String): BackendSession = decode(http.request("GET", "/api/v1/sessions/${safeId(id)}"))

    override suspend fun event(id: String, event: BackendEvent): BackendSession = decode(http.request(
        "POST", "/api/v1/sessions/${safeId(id)}/events", http.json.encodeToString(event).toByteArray()))

    override suspend fun getFrame(id: String): ByteArray =
        http.requestBytes("GET", "/api/v1/sessions/${safeId(id)}/image")

    override suspend fun uploadVideo(id: String, version: Int, file: File, key: String): BackendSession {
        VideoUploadLimits.validateFile(file)
        val boundary = "Circuitly${UUID.randomUUID()}"
        // The deployed MP4 endpoint deliberately retains its legacy route/field name.
        val prefix = ("--$boundary\r\nContent-Disposition: form-data; name=\"expected_session_version\"\r\n\r\n$version\r\n" +
            "--$boundary\r\nContent-Disposition: form-data; name=\"image\"; filename=\"circuit.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").toByteArray()
        val suffix = "\r\n--$boundary--\r\n".toByteArray()
        val context = currentCoroutineContext()
        val size = file.length()
        val body = StreamingRequestBody(prefix.size.toLong() + size + suffix.size) { output ->
            check(file.length() == size) { "The video changed. Select it again." }
            output.write(prefix)
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                var total = 0L
                while (true) {
                    context.ensureActive()
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    check(total <= size) { "The video changed. Select it again." }
                    output.write(buffer, 0, count)
                }
                check(total == size) { "The video changed. Select it again." }
            }
            output.write(suffix)
        }
        return decode(http.request("POST", "/api/v1/sessions/${safeId(id)}/image",
            contentType = "multipart/form-data; boundary=$boundary", idempotencyKey = key, streamBody = body))
    }

    private fun decode(value: String): BackendSession = http.json.decodeFromString(value)
    private fun safeId(id: String): String = UUID.fromString(id).toString()
}
