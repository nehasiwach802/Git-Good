package com.example.gitgood.data.backend

import kotlinx.serialization.encodeToString
import java.io.ByteArrayOutputStream
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

    override suspend fun upload(id: String, version: Int, bytes: ByteArray, mime: String, key: String): BackendSession {
        require(bytes.isNotEmpty() && bytes.size <= 5 * 1024 * 1024) { "Choose an image smaller than 5 MiB." }
        require(mime in setOf("image/jpeg", "image/png")) { "Choose a JPEG or PNG image." }
        val boundary = "Circuitly${UUID.randomUUID()}"
        val body = ByteArrayOutputStream().apply {
            fun text(value: String) { write(value.toByteArray(Charsets.UTF_8)) }
            text("--$boundary\r\nContent-Disposition: form-data; name=\"expected_session_version\"\r\n\r\n$version\r\n")
            val extension = if (mime == "image/png") "png" else "jpg"
            text("--$boundary\r\nContent-Disposition: form-data; name=\"image\"; filename=\"circuit.$extension\"\r\nContent-Type: $mime\r\n\r\n")
            write(bytes)
            text("\r\n--$boundary--\r\n")
        }.toByteArray()
        return decode(http.request("POST", "/api/v1/sessions/${safeId(id)}/image", body, "multipart/form-data; boundary=$boundary", key))
    }

    private fun decode(value: String): BackendSession = http.json.decodeFromString(value)
    private fun safeId(id: String): String = UUID.fromString(id).toString()
}
