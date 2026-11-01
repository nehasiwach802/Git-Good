package com.example.gitgood.viewModel

import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.gitgood.data.backend.*
import com.example.gitgood.data.model.Experiment
import com.example.gitgood.ui.theme.screen.conversation.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.util.UUID
import javax.inject.Inject

@HiltViewModel
class ConversationViewModel @Inject constructor(
    private val repository: SessionApi,
    private val saved: SavedStateHandle,
    private val account: IdTokenProvider,
    private val images: SessionImageStore
) : ViewModel() {
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    val uiState = MutableStateFlow(ConversationUiState(experimentName = saved["name"] ?: "Circuit review", isDemo = false))
    val reviewContract = MutableStateFlow(saved.get<String>("contract")?.let { runCatching { json.parseToJsonElement(it).jsonObject }.getOrNull() } ?: JsonObject(emptyMap()))
    val session = MutableStateFlow(saved.get<String>("snapshot")?.let { runCatching { json.decodeFromString<BackendSession>(it) }.getOrNull() })
    private var operation: Job? = null
    private var poller: Job? = null
    private var foreground = false
    private var owner: String? = saved["owner"]
    private var generation = 0
    private var activeImage: Uri? = saved.get<String>("imagePath")?.let(images::preview)

    init {
        session.value?.let(::applySnapshot)
        uiState.value = uiState.value.copy(draft = saved["draft"] ?: "")
        if (saved.get<String>("pendingEvent") != null || saved.get<String>("createRequest") != null) {
            uiState.value = uiState.value.copy(canSend = false, errorMessage = "A request was interrupted. Retry to resume it safely.")
        }
    }

    fun resetForAccount(uid: String?) {
        if (owner == uid) return
        generation++
        operation?.cancel(); poller?.cancel()
        session.value = null
        saved.get<String>("imagePath")?.let(images::remove)
        saved.keys().toList().forEach { saved.remove<Any>(it) }
        activeImage = null; owner = uid; saved["owner"] = uid
        reviewContract.value = JsonObject(emptyMap())
        uiState.value = ConversationUiState("Circuit review", isDemo = false)
    }

    fun start(experiment: Experiment, uri: Uri, description: String) {
        resetForAccount(account.userId)
        if (!experiment.canStart) {
            uiState.value = uiState.value.copy(errorMessage = "This experiment’s backend workflow is not available yet.")
            return
        }
        if (operation?.isActive == true) return
        if (session.value?.closed == false || saved.get<String>("createRequest") != null) {
            uiState.value = uiState.value.copy(errorMessage = "An existing conversation is still open. Exit it before starting another.")
            return
        }
        saved.get<String>("imagePath")?.let(images::remove)
        saved.remove<String>("imagePath"); saved.remove<String>("imageMime")
        activeImage = null
        session.value = null; saved.remove<String>("snapshot")
        saved["contract"] = experiment.reviewContract.toString()
        reviewContract.value = experiment.reviewContract
        saved["name"] = experiment.name
        saved["createRequest"] = json.encodeToString(CreateSession(experiment.backendId, experiment.version, description.trim()))
        saved["createKey"] = uuid(); saved["uploadKey"] = uuid()
        saved.remove<String>("draft")
        saved.remove<Boolean>("creationStarted")
        saved.remove<Int>("uploadVersion"); saved.remove<String>("pendingEvent")
        uiState.value = ConversationUiState(experiment.name, isDemo = false)
        val imageFileName = "${saved.get<String>("createKey")}.image"
        runOperation {
            // Validate and retain the image before sending any create request.
            val image = try { images.prepare(uri, imageFileName) }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) {
                saved.remove<String>("createRequest")
                throw failure
            }
            saved["imagePath"] = image.path; saved["imageMime"] = image.mime
            activeImage = images.preview(image.path)
            initializeSession()
        }
    }

    private suspend fun initializeSession() {
        var current = session.value
        // Before the first request, a valid cached image is mandatory. An uncertain
        // create can still be reconciled with its original key if that image was lost.
        val preparedBytes = if (current == null && saved.get<Boolean>("creationStarted") != true) readPreparedImage() else null
        if (current == null) {
            val request = saved.get<String>("createRequest") ?: error("Return home and start a conversation.")
            saved["creationStarted"] = true
            current = repository.create(json.decodeFromString(request), saved.get<String>("createKey")!!)
            applySnapshot(current)
        }
        if (current.state == "awaiting_image") {
            val bytes = preparedBytes ?: readPreparedImage()
            val version = saved.get<Int>("uploadVersion") ?: current.session_version.also { saved["uploadVersion"] = it }
            applySnapshot(repository.upload(current.session_id, version, bytes, saved.get<String>("imageMime")!!, saved.get<String>("uploadKey")!!))
        }
        saved.remove<String>("createRequest")
    }

    private suspend fun readPreparedImage(): ByteArray {
        try {
            val path = saved.get<String>("imagePath") ?: error("Return home and select the image again.")
            check(saved.get<String>("imageMime") != null) { "Return home and select the image again." }
            return images.read(path)
        } catch (cancelled: CancellationException) { throw cancelled
        } catch (failure: Exception) {
            if (saved.get<Boolean>("creationStarted") != true) saved.remove<String>("createRequest")
            throw failure
        }
    }

    fun draft(value: String) { saved["draft"] = value; uiState.value = uiState.value.copy(draft = value) }
    fun sendMessage() {
        val text = uiState.value.draft.trim()
        if (text.isBlank() || text.codePointCount(0, text.length) > 2000) return
        submit("message", buildJsonObject { put("text", text) })
    }
    fun submit(type: String, payload: JsonObject) {
        val current = session.value ?: return
        if (operation?.isActive == true || current.busy || current.closed || saved.get<String>("pendingEvent") != null) return
        saved["pendingEvent"] = json.encodeToString(BackendEvent(uuid(), current.session_version, type, payload))
        retry()
    }
    /** Leave locally: no close/delete event and no waiting for server processing. */
    fun exit() {
        generation++
        foreground = false
        operation?.cancel()
        poller?.cancel()
        operation = null
        poller = null
        session.value = null
        // Keep the private image path only for cleanup on the next start/account reset.
        saved.keys().filterNot { it in setOf("owner", "imagePath", "imageMime") }
            .forEach { saved.remove<Any>(it) }
        reviewContract.value = JsonObject(emptyMap())
        uiState.value = ConversationUiState(
            experimentName = uiState.value.experimentName,
            isDemo = false, canSend = false, exited = true
        )
    }
    fun retry() = runOperation {
        val pending = saved.get<String>("pendingEvent")
        if (pending != null) {
            val event = json.decodeFromString<BackendEvent>(pending)
            val result = repository.event(session.value!!.session_id, event)
            saved.remove<String>("pendingEvent")
            if (event.type == "message") draft("")
            applySnapshot(result)
        } else if (saved.get<String>("createRequest") != null) initializeSession()
        else session.value?.let { applySnapshot(repository.get(it.session_id)) }
    }
    fun setForeground(value: Boolean) {
        foreground = value
        if (value) {
            if (session.value != null && operation?.isActive != true && saved.get<String>("pendingEvent") == null && saved.get<String>("createRequest") == null) retry()
            else startPolling()
        } else poller?.cancel()
    }
    private fun runOperation(block: suspend () -> Unit) {
        if (operation?.isActive == true) return
        val currentGeneration = generation
        poller?.cancel()
        operation = viewModelScope.launch {
            uiState.value = uiState.value.copy(isSending = true, errorMessage = null)
            try { block()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                if (currentGeneration != generation) return@launch
                if (e is BackendException && e.status == 409) {
                    // Stale confirmations must require a new explicit review, never automatic replay.
                    saved.remove<String>("pendingEvent")
                    session.value?.let {
                        try { applySnapshot(repository.get(it.session_id)) }
                        catch (cancelled: CancellationException) { throw cancelled }
                        catch (_: Exception) { /* Keep the last snapshot; a later retry refreshes it. */ }
                    }
                    if (session.value?.state == "awaiting_image") {
                        saved.remove<Int>("uploadVersion")
                        saved["uploadKey"] = uuid()
                    }
                } else if (e is BackendException && e.status in setOf(400, 403, 404, 413, 415, 422)) {
                    saved.remove<String>("pendingEvent")
                    if (session.value == null) {
                        saved.remove<String>("createRequest")
                        saved.remove<Boolean>("creationStarted")
                    }
                }
                uiState.value = uiState.value.copy(errorMessage = e.message ?: "Connection failed. Retry to resume the same operation.")
            } finally {
                if (currentGeneration == generation) {
                    uiState.value = uiState.value.copy(isSending = false,
                        canSend = session.value?.let { !it.busy && !it.closed } == true && saved.get<String>("pendingEvent") == null && saved.get<String>("createRequest") == null)
                    startPolling()
                }
            }
        }
    }
    private fun applySnapshot(value: BackendSession) {
        if (session.value?.let { it.session_id == value.session_id && it.session_version > value.session_version } == true) return
        session.value = value; saved["snapshot"] = json.encodeToString(value)
        if (value.closed) {
            saved.remove<String>("createRequest")
            saved.remove<String>("pendingEvent")
            saved.remove<Boolean>("creationStarted")
            saved.remove<Int>("uploadVersion")
        }
        val firstUser = value.messages.firstOrNull { it.role == "user" }?.id
        uiState.value = uiState.value.copy(
            messages = value.messages.map {
                ConversationMessageUi(it.id, when (it.role) { "user" -> MessageSender.USER; "assistant" -> MessageSender.ASSISTANT; else -> MessageSender.SYSTEM }, it.text,
                    if (it.id == firstUser) activeImage else null)
            }, isDemo = false, notice = if (value.simulated) "Synthetic experiment · Test results do not validate a real circuit." else null,
            status = value.state.replace('_', ' '), canSend = !value.busy && !value.closed,
            exited = value.closed,
            errorMessage = value.error?.let { (it["message"] as? JsonPrimitive)?.content }
        )
    }
    private fun startPolling() {
        poller?.cancel()
        if (!foreground || session.value?.busy != true) return
        poller = viewModelScope.launch {
            while (isActive && foreground && session.value?.busy == true) {
                delay(2000)
                if (operation?.isActive == true) continue
                try { applySnapshot(repository.get(session.value!!.session_id))
                } catch (e: CancellationException) { throw e
                } catch (e: Exception) {
                    uiState.value = uiState.value.copy(errorMessage = e.message ?: "Could not refresh the conversation.")
                    break
                }
            }
        }
    }
    private fun uuid() = UUID.randomUUID().toString()
}
