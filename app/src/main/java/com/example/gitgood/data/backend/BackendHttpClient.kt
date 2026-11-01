package com.example.gitgood.data.backend

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import java.net.HttpURLConnection
import java.net.URL

class StreamingRequestBody(val length: Long, val writeTo: (java.io.OutputStream) -> Unit)

interface IdTokenProvider {
    val userId: String?
    suspend fun token(forceRefresh: Boolean): String
}

/** No automatic mutation retries. Callers retain idempotency/event IDs for explicit retry. */
class BackendHttpClient(
    private val tokens: IdTokenProvider,
    private val baseUrl: String = "https://backend-circuitly.onrender.com"
) {
    val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    suspend fun request(method: String, path: String, body: ByteArray? = null,
                        contentType: String = "application/json", idempotencyKey: String? = null,
                        streamBody: StreamingRequestBody? = null): String =
        requestBytes(method, path, body, contentType, idempotencyKey, streamBody, "application/json").toString(Charsets.UTF_8)

    suspend fun requestBytes(method: String, path: String, body: ByteArray? = null,
                        contentType: String = "application/json", idempotencyKey: String? = null,
                        streamBody: StreamingRequestBody? = null, accept: String = "*/*"): ByteArray {
        require(body == null || streamBody == null)
        val owner = tokens.userId ?: throw BackendException(401, "Please sign in again.")
        for (attempt in 0..1) {
            val token = tokens.token(attempt == 1)
            if (tokens.userId != owner) throw BackendException(401, "Account changed. Please sign in again.")
            val response = withContext(Dispatchers.IO) {
                val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
                try {
                    connection.requestMethod = method
                    connection.instanceFollowRedirects = false
                    connection.connectTimeout = 30_000
                    connection.readTimeout = 90_000
                    connection.setRequestProperty("Authorization", "Bearer $token")
                    connection.setRequestProperty("Accept", accept)
                    idempotencyKey?.let { connection.setRequestProperty("Idempotency-Key", it) }
                    if (streamBody != null) {
                        connection.doOutput = true
                        connection.setRequestProperty("Content-Type", contentType)
                        connection.setFixedLengthStreamingMode(streamBody.length)
                        connection.outputStream.use(streamBody.writeTo)
                    }
                    body?.let {
                        connection.doOutput = true
                        connection.setRequestProperty("Content-Type", contentType)
                        connection.setFixedLengthStreamingMode(it.size)
                        connection.outputStream.use { stream -> stream.write(it) }
                    }
                    val status = connection.responseCode
                    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
                    val bytes = stream?.use { it.readNBytesCompat(8 * 1024 * 1024) } ?: byteArrayOf()
                    status to bytes
                } finally { connection.disconnect() }
            }
            if (tokens.userId != owner) throw BackendException(401, "Account changed. Response discarded.")
            if (response.first == 401 && attempt == 0) continue
            if (response.first !in 200..299) throw BackendException(response.first, errorMessage(response.first, response.second.toString(Charsets.UTF_8)))
            return response.second
        }
        throw BackendException(401, "Please sign in again.")
    }

    private fun errorMessage(status: Int, body: String): String {
        val root = runCatching { json.parseToJsonElement(body).jsonObject }.getOrNull()
        val detail = root?.get("detail")
        return when (detail) {
            is JsonPrimitive -> detail.content
            is JsonObject -> (detail["message"] as? JsonPrimitive)?.content
            else -> null
        } ?: when (status) {
            401 -> "Your login expired. Please sign in again."
            409 -> "The session changed. Review the latest state before trying again."
            413 -> "The video exceeds the server upload limit (50 MiB)."
            415 -> "Choose an MP4 video. Other media formats are not supported."
            422 -> "The server rejected the submitted fields. Check your input."
            else -> "The server returned HTTP $status. Please try again."
        }
    }
}

private fun java.io.InputStream.readNBytesCompat(limit: Int): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (true) {
        val count = read(buffer)
        if (count < 0) break
        require(output.size() + count <= limit) { "Server response is too large." }
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}
