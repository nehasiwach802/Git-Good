package com.example.gitgood.data.backend

import com.sun.net.httpserver.HttpServer
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.net.InetSocketAddress

class LiveSessionRepositoryTest {
    private lateinit var server: HttpServer
    private lateinit var client: BackendHttpClient
    private lateinit var repository: LiveSessionRepository
    private var uid: String? = "student"
    private val refreshes = mutableListOf<Boolean>()
    private val calls = mutableListOf<Call>()
    private var handler: (Call) -> Pair<Int, String> = { 200 to snapshot }
    private data class Call(val path: String, val method: String, val auth: String?, val key: String?, val contentType: String?, val body: String)

    @Before fun setup() {
        server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        server.createContext("/") { exchange ->
            val call = Call(exchange.requestURI.path, exchange.requestMethod,
                exchange.requestHeaders.getFirst("Authorization"), exchange.requestHeaders.getFirst("Idempotency-Key"),
                exchange.requestHeaders.getFirst("Content-Type"), exchange.requestBody.bufferedReader().readText())
            calls.add(call)
            val (status, text) = handler(call)
            val body = text.toByteArray()
            exchange.sendResponseHeaders(status, body.size.toLong())
            exchange.responseBody.use { it.write(body) }
        }
        server.start()
        client = BackendHttpClient(object : IdTokenProvider {
            override val userId get() = uid
            override suspend fun token(forceRefresh: Boolean): String {
                refreshes.add(forceRefresh)
                return if (forceRefresh) "fresh-token" else "initial-token"
            }
        }, "http://127.0.0.1:${server.address.port}")
        repository = LiveSessionRepository(client)
    }
    @After fun cleanup() { server.stop(0) }

    @Test fun catalogUsesAuthenticatedServerIdsAndVersions() = runBlocking {
        handler = { 200 to """{"experiments":[{"experiment_id":"synthetic-rc","version":"2","name":"RC demo","simulated":true,"workflow_approved":false,"review_contract":{}}]}""" }
        val experiment = repository.experiments().single()
        assertEquals("synthetic-rc@2", experiment.key)
        assertTrue(experiment.simulated)
        assertEquals("/api/v1/experiments", calls.single().path)
        assertEquals("Bearer initial-token", calls.single().auth)
    }
    @Test fun createParsesBareSnapshotAndSendsDescription() = runBlocking {
        val result = repository.create(CreateSession("synthetic-rc", "2", "My circuit"), "stable-key")
        assertEquals(7, result.session_version)
        assertEquals("stable-key", calls.single().key)
        assertEquals("/api/v1/sessions", calls.single().path)
        val body = Json.parseToJsonElement(calls.single().body).jsonObject
        assertEquals("My circuit", body["description"]?.jsonPrimitive?.content)
        assertFalse(body.containsKey("data"))
    }
    @Test fun uploadUsesSingularImageRouteAndExactMultipartFields() = runBlocking {
        repository.upload(id, 7, byteArrayOf(1, 2, 3), "image/png", "upload-key")
        val call = calls.single()
        assertEquals("/api/v1/sessions/$id/image", call.path)
        assertTrue(call.contentType!!.startsWith("multipart/form-data; boundary="))
        assertTrue(call.body.contains("name=\"expected_session_version\"\r\n\r\n7"))
        assertTrue(call.body.contains("name=\"image\"; filename=\"circuit.png\""))
        assertEquals("upload-key", call.key)
    }
    @Test fun confirmationRevisionIsNestedInPayload() = runBlocking {
        repository.event(id, BackendEvent(id, 7, "confirm_candidate", buildJsonObject {
            put("candidate_revision", 3); put("acknowledgement", "reviewed_all_connections_and_board")
        }))
        val body = Json.parseToJsonElement(calls.single().body).jsonObject
        assertEquals(7, body["expected_session_version"]?.jsonPrimitive?.int)
        assertFalse(body.containsKey("candidate_revision"))
        assertEquals(3, body["payload"]?.jsonObject?.get("candidate_revision")?.jsonPrimitive?.int)
    }
    @Test fun unauthorizedRefreshKeepsTheSameMutationKeyAndBody() = runBlocking {
        handler = { if (it.auth == "Bearer initial-token") 401 to "{}" else 201 to snapshot }
        repository.create(CreateSession("x", "1", "description"), "unchanged-key")
        assertEquals(listOf(false, true), refreshes)
        assertEquals(2, calls.size)
        assertEquals(calls[0].key, calls[1].key)
        assertEquals(calls[0].body, calls[1].body)
    }
    @Test fun staleConfirmationIsNotAutomaticallyReplayed() = runBlocking {
        handler = { 409 to """{"detail":{"code":"stale_session","message":"Review the new revision"}}""" }
        try {
            repository.event(id, BackendEvent(id, 7, "confirm_candidate", buildJsonObject { put("candidate_revision", 3) }))
            fail("Expected conflict")
        } catch (e: BackendException) { assertEquals(409, e.status); assertEquals("Review the new revision", e.message) }
        assertEquals(1, calls.size)
    }
    @Test fun exitClosesWithoutDeletingOrClaimingResolution() = runBlocking {
        repository.event(id, BackendEvent(id, 7, "close_session", buildJsonObject { put("resolved", false) }))
        val call = calls.single()
        assertEquals("POST", call.method)
        assertEquals("/api/v1/sessions/$id/events", call.path)
        val body = Json.parseToJsonElement(call.body).jsonObject
        assertEquals("close_session", body["type"]?.jsonPrimitive?.content)
        assertEquals(false, body["payload"]?.jsonObject?.get("resolved")?.jsonPrimitive?.boolean)
    }
    @Test fun serverFailureDoesNotAutomaticallyDuplicateCreate() = runBlocking {
        handler = { 503 to "{}" }
        try { repository.create(CreateSession("x", "1", "description"), "stable-key"); fail("Expected server failure") }
        catch (e: BackendException) { assertEquals(503, e.status) }
        assertEquals(1, calls.size)
    }
    @Test fun signedOutRequestsNeverReachServer() = runBlocking {
        uid = null
        try { repository.experiments(); fail("Expected authentication error") }
        catch (e: BackendException) { assertEquals(401, e.status) }
        assertTrue(calls.isEmpty())
    }
    @Test fun accountChangeDiscardsResponse() = runBlocking {
        handler = { uid = "different-student"; 200 to snapshot }
        try { repository.get(id); fail("Expected account isolation") }
        catch (e: BackendException) { assertEquals(401, e.status) }
    }
    @Test fun unsupportedImageDoesNotUpload() = runBlocking {
        try { repository.upload(id, 7, byteArrayOf(1), "image/webp", "key"); fail("Expected rejection") }
        catch (_: IllegalArgumentException) { }
        assertTrue(calls.isEmpty())
    }
    companion object {
        private const val id = "00000000-0000-4000-8000-000000000001"
        private val snapshot = """{"session_id":"$id","session_version":7,"state":"awaiting_review","experiment_id":"synthetic-rc","experiment_version":"2","description":"My circuit","candidate_revision":3,"candidate":{},"messages":[{"id":"m1","role":"assistant","text":"Review connections","created_at":"now"}],"actions":[{"type":"review_candidate","candidate_revision":3}],"simulated":true,"ml1":{},"ml3":{}}"""
    }
}
