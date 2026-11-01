package com.example.gitgood.viewModel

import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import com.example.gitgood.data.backend.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ConversationViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val json = Json { encodeDefaults = true }
    private val api = FakeApi()
    private val images = FakeImages()
    private var uid: String? = "student"
    private val tokens = object : IdTokenProvider {
        override val userId get() = uid
        override suspend fun token(forceRefresh: Boolean) = "unused"
    }
    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun cleanup() { Dispatchers.resetMain() }

    private fun viewModel(saved: SavedStateHandle) = ConversationViewModel(api, saved, tokens, images)
    private fun saved(current: BackendSession? = null, pending: BackendEvent? = null) = SavedStateHandle().apply {
        set("owner", "student")
        current?.let { set("snapshot", json.encodeToString(it)) }
        pending?.let { set("pendingEvent", json.encodeToString(it)) }
    }
    private fun pendingCreate() = saved().apply {
        set("createRequest", json.encodeToString(CreateSession("rc", "1", "Circuit")))
        set("createKey", "original-create-key")
        set("uploadKey", "original-upload-key")
    }

    @Test fun retryWithoutPreparedImageNeverCreatesSession() = runTest(dispatcher) {
        val state = pendingCreate()
        val vm = viewModel(state)
        vm.retry(); runCurrent()
        assertEquals(0, api.creates)
        assertNotNull(vm.uiState.value.errorMessage)
        vm.exit()
        assertTrue(vm.uiState.value.exited)
    }
    @Test fun retryWithUnreadableImageNeverCreatesSession() = runTest(dispatcher) {
        val state = pendingCreate().apply { set("imagePath", "missing"); set("imageMime", "image/png") }
        images.readFailure = true
        val vm = viewModel(state)
        vm.retry(); runCurrent()
        assertEquals(0, api.creates)
        vm.exit()
        assertTrue(vm.uiState.value.exited)
    }
    @Test fun uncertainCreateKeepsKeyAndCanBeExitedLocallyEvenIfImageWasLost() = runTest(dispatcher) {
        val state = pendingCreate().apply { set("creationStarted", true) }
        val vm = viewModel(state)
        vm.retry(); runCurrent()
        assertEquals(1, api.creates)
        assertEquals("original-create-key", api.createKey)
        assertEquals("awaiting_image", vm.session.value?.state)
        vm.exit(); runCurrent()
        assertTrue(api.events.isEmpty())
        assertTrue(vm.uiState.value.exited)
        assertNull(state.get<String>("createRequest"))
        assertNull(state.get<String>("pendingEvent"))
    }
    @Test fun failedMessageRetryRetainsExactEventAndDraft() = runTest(dispatcher) {
        val state = saved(snapshot())
        val vm = viewModel(state)
        vm.draft("Explain this")
        api.eventFailure = BackendException(503, "Temporarily unavailable")
        vm.sendMessage(); runCurrent()
        assertEquals("Explain this", vm.uiState.value.draft)
        assertFalse(vm.uiState.value.canSend)
        api.eventFailure = null
        vm.retry(); runCurrent()
        assertEquals(api.events[0], api.events[1])
        assertEquals("", vm.uiState.value.draft)
    }
    @Test fun staleConfirmationRefreshesAndRequiresNewExplicitEvent() = runTest(dispatcher) {
        val vm = viewModel(saved(snapshot()))
        api.eventFailure = BackendException(409, "Candidate changed")
        api.latest = snapshot(version = 9, revision = 4)
        vm.submit("confirm_candidate", buildJsonObject { put("candidate_revision", 3) })
        runCurrent()
        assertEquals(9, vm.session.value?.session_version)
        api.eventFailure = null
        vm.retry(); runCurrent()
        assertEquals(1, api.events.size)
        vm.submit("confirm_candidate", buildJsonObject { put("candidate_revision", 4) }); runCurrent()
        assertEquals(9, api.events.last().expected_session_version)
        assertNotEquals(api.events.first().event_id, api.events.last().event_id)
    }
    @Test fun busySessionExitsImmediatelyWithoutServerEvent() = runTest(dispatcher) {
        val vm = viewModel(saved(snapshot(state = "extracting")))
        vm.exit(); runCurrent()
        assertTrue(api.events.isEmpty())
        assertTrue(vm.uiState.value.exited)
        assertNull(vm.uiState.value.errorMessage)
        assertNull(vm.session.value)
    }
    @Test fun pendingEventIsNotSentOnExit() = runTest(dispatcher) {
        val pending = BackendEvent("pending", 7, "message", buildJsonObject { put("text", "Question") })
        val state = saved(snapshot(), pending)
        val vm = viewModel(state)
        vm.exit(); runCurrent()
        assertTrue(vm.uiState.value.exited)
        assertTrue(api.events.isEmpty())
        assertNull(state.get<String>("pendingEvent"))
        assertNull(state.get<String>("snapshot"))
    }
    @Test fun exitDuringMessageRequestReturnsImmediatelyAndIgnoresLateResponse() = runTest(dispatcher) {
        val vm = viewModel(saved(snapshot()))
        val response = CompletableDeferred<BackendSession>()
        api.eventGate = response
        vm.draft("Question")
        vm.sendMessage(); runCurrent()
        assertTrue(vm.uiState.value.isSending)
        vm.exit()
        assertTrue(vm.uiState.value.exited)
        assertFalse(vm.uiState.value.isSending)
        response.complete(snapshot(version = 8))
        runCurrent()
        assertNull(vm.session.value)
        assertTrue(vm.uiState.value.exited)
        assertEquals(1, api.events.size)
        assertEquals("message", api.events.single().type)
    }
    @Test fun accountResetClearsPendingRequestsAndReviewMetadata() = runTest(dispatcher) {
        val state = saved(snapshot()).apply { set("contract", "{\"analysis\":{}}") }
        val vm = viewModel(state)
        vm.resetForAccount("other-student")
        assertNull(vm.session.value)
        assertTrue(vm.reviewContract.value.isEmpty())
        assertNull(state.get<String>("snapshot"))
        assertEquals("other-student", state.get<String>("owner"))
    }
    @Test fun olderSnapshotNeverOverwritesNewerRevision() = runTest(dispatcher) {
        val vm = viewModel(saved(snapshot(version = 9, revision = 4)))
        api.latest = snapshot(version = 7, revision = 3)
        vm.retry(); runCurrent()
        assertEquals(9, vm.session.value?.session_version)
        assertEquals(4, vm.session.value?.candidate_revision)
    }

    private class FakeImages : SessionImageStore {
        var readFailure = false
        override suspend fun prepare(uri: Uri, fileName: String) = error("Not used")
        override suspend fun read(path: String): ByteArray {
            if (readFailure) throw java.io.IOException("Image unavailable")
            return byteArrayOf(1)
        }
        override fun preview(path: String): Uri? = null
        override fun remove(path: String) {}
    }
    private class FakeApi : SessionApi {
        var creates = 0
        var createKey: String? = null
        var latest = snapshot()
        var eventFailure: Exception? = null
        var eventGate: CompletableDeferred<BackendSession>? = null
        val events = mutableListOf<BackendEvent>()
        override suspend fun experiments() = emptyList<BackendExperiment>()
        override suspend fun create(request: CreateSession, key: String): BackendSession {
            creates++; createKey = key
            return snapshot(state = "awaiting_image")
        }
        override suspend fun get(id: String) = latest
        override suspend fun event(id: String, event: BackendEvent): BackendSession {
            events.add(event)
            eventFailure?.let { throw it }
            eventGate?.let { return it.await() }
            return latest.copy(session_version = event.expected_session_version + 1,
                state = if (event.type == "close_session") "closed" else latest.state)
        }
        override suspend fun upload(id: String, version: Int, bytes: ByteArray, mime: String, key: String) = latest
    }
    companion object {
        private fun snapshot(version: Int = 7, revision: Int = 3, state: String = "awaiting_review") = BackendSession(
            "00000000-0000-4000-8000-000000000001", version, state, "rc", "1", "Circuit", revision)
    }
}
