package com.example.gitgood.viewModel

import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.gitgood.data.backend.*
import com.example.gitgood.data.model.Experiment
import com.example.gitgood.data.model.wirereview.*
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
    private val videos: SessionVideoStore
) : ViewModel() {
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    val uiState = MutableStateFlow(ConversationUiState(experimentName = saved["name"] ?: "Circuit review", isDemo = false))
    val reviewContract = MutableStateFlow(saved.get<String>("contract")?.let { runCatching { json.parseToJsonElement(it).jsonObject }.getOrNull() } ?: JsonObject(emptyMap()))
    val session = MutableStateFlow(saved.get<String>("snapshot")?.let { runCatching { json.decodeFromString<BackendSession>(it) }.getOrNull() })
    private var operation: Job? = null
    private var poller: Job? = null
    private var frameJob: Job? = null
    private var requestedFrameHash: String? = null
    private var foreground = false
    private var owner: String? = saved["owner"]
    private var generation = 0
    private var activeFrame: Uri? = saved.get<String>("framePath")?.let(videos::preview)

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
        operation?.cancel(); poller?.cancel(); frameJob?.cancel()
        session.value = null
        saved.get<String>("videoPath")?.let(videos::remove)
        saved.get<String>("framePath")?.let(videos::remove)
        saved.keys().toList().forEach { saved.remove<Any>(it) }
        activeFrame = null; owner = uid; saved["owner"] = uid
        reviewContract.value = JsonObject(emptyMap())
        uiState.value = ConversationUiState("Circuit review", isDemo = false)
    }

    fun startVideo(experiment: Experiment, uri: Uri, description: String) {
        resetForAccount(account.userId)
        if (description.isBlank() || description.codePointCount(0, description.length) > 2000) {
            uiState.value = uiState.value.copy(errorMessage = "Add a description of up to 2,000 characters.")
            return
        }
        if (!experiment.canStart) {
            uiState.value = uiState.value.copy(errorMessage = "This experiment’s backend workflow is not available yet.")
            return
        }
        if (operation?.isActive == true) return
        if (session.value?.closed == false || saved.get<String>("createRequest") != null) {
            uiState.value = uiState.value.copy(errorMessage = "An existing conversation is still open. Exit it before starting another.")
            return
        }
        saved.get<String>("videoPath")?.let(videos::remove)
        saved.get<String>("framePath")?.let(videos::remove)
        saved.remove<String>("videoPath"); saved.remove<String>("framePath"); saved.remove<String>("frameHash")
        activeFrame = null
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
        val videoFileName = "${saved.get<String>("createKey")}.mp4"
        runOperation {
            uiState.value = uiState.value.copy(status = "Preparing video…")
            // Validate and retain an immutable private copy before creating a session.
            val video = try { videos.prepare(uri, videoFileName) }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) {
                saved.remove<String>("createRequest")
                throw failure
            }
            saved["videoPath"] = video.path
            initializeSession()
        }
    }

    private suspend fun initializeSession() {
        var current = session.value
        // Before the first request, a valid cached video is mandatory. An uncertain
        // create can still be reconciled with its original key if that video was lost.
        val preparedFile = if (current == null && saved.get<Boolean>("creationStarted") != true) readPreparedVideo() else null
        if (current == null) {
            val request = saved.get<String>("createRequest") ?: error("Return home and start a conversation.")
            saved["creationStarted"] = true
            current = repository.create(json.decodeFromString(request), saved.get<String>("createKey")!!)
            applySnapshot(current)
        }
        if (current.state == "awaiting_image") {
            val file = preparedFile ?: readPreparedVideo()
            val version = saved.get<Int>("uploadVersion") ?: current.session_version.also { saved["uploadVersion"] = it }
            uiState.value = uiState.value.copy(status = "Uploading video…")
            applySnapshot(repository.uploadVideo(current.session_id, version, file, saved.get<String>("uploadKey")!!))
        }
        saved.remove<String>("createRequest")
    }

    private suspend fun readPreparedVideo(): java.io.File {
        try {
            val path = saved.get<String>("videoPath") ?: error("Return home and select the video again.")
            return videos.file(path)
        } catch (cancelled: CancellationException) { throw cancelled
        } catch (failure: Exception) {
            if (saved.get<Boolean>("creationStarted") != true) saved.remove<String>("createRequest")
            throw failure
        }
    }

    fun reviewWire(identity: ReviewIdentity, action: WireReviewAction) {
        val current = uiState.value.wireReview ?: return
        if (current.identity != identity || identity.account != account.userId || uiState.value.isSending || !uiState.value.canSend) return
        uiState.value = uiState.value.copy(wireReview = reduceWireReview(current, action))
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
        frameJob?.cancel()
        operation = null
        poller = null
        session.value = null
        // Keep the private video/frame paths only for cleanup on the next start/account reset.
        saved.keys().filterNot { it in setOf("owner", "videoPath", "framePath") }
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
        val imageHash = (value.image?.get("sha256") as? JsonPrimitive)?.contentOrNull
        if (imageHash != saved.get<String>("frameHash")) activeFrame = null
        session.value = value; saved["snapshot"] = json.encodeToString(value)
        if (value.closed) {
            saved.remove<String>("createRequest")
            saved.remove<String>("pendingEvent")
            saved.remove<Boolean>("creationStarted")
            saved.remove<Int>("uploadVersion")
        }
        val parsedReview = parseWireReview(value, owner)
        val previousReview = uiState.value.wireReview
        val nextReview = if (parsedReview?.identity == previousReview?.identity) previousReview else parsedReview?.copy(
            notice = if (previousReview?.dirty == true) "Frame, board or revision changed. Local wire edits were cleared for a fresh review." else null
        )
        val firstUser = value.messages.firstOrNull { it.role == "user" }?.id
        val media = value.ml1["media"] as? JsonObject
        val selectedFrame = (media?.get("selected_frame_id") as? JsonPrimitive)?.contentOrNull
        val frameInfo = (media?.get("frames") as? JsonArray)?.mapNotNull { it as? JsonObject }
            ?.firstOrNull { (it["id"] as? JsonPrimitive)?.contentOrNull == selectedFrame }
        val timestamp = (frameInfo?.get("timestamp_s") as? JsonPrimitive)?.doubleOrNull
        val caption = if (selectedFrame != null) "Review frame $selectedFrame" + (timestamp?.let { " at ${it}s" } ?: "") else "Frame selected from your video"
        val messages = value.messages.map {
            ConversationMessageUi(it.id, when (it.role) { "user" -> MessageSender.USER; "assistant" -> MessageSender.ASSISTANT; else -> MessageSender.SYSTEM }, it.text,
                if (it.id == firstUser) activeFrame else null,
                if (it.id == firstUser && activeFrame != null) caption else null)
        }
        val initial = if (firstUser == null) listOf(ConversationMessageUi("video-${value.session_id}", MessageSender.USER,
            value.description + "\nVideo attached", activeFrame, if (activeFrame != null) caption else null)) else emptyList()
        uiState.value = uiState.value.copy(
            messages = initial + messages,
            isProcessing = value.busy, reviewFrameUri = activeFrame, frameCaption = caption, wireReview = nextReview,
            isDemo = false, notice = if (value.simulated) "Synthetic experiment · Test results do not validate a real circuit." else null,
            status = when (value.state) {
                "awaiting_image" -> "Ready to upload video"
                "extracting" -> "Processing video…"
                "awaiting_review" -> "Review the selected video frame"
                "diagnosing" -> "Checking circuit…"
                else -> value.state.replace('_', ' ')
            }, canSend = !value.busy && !value.closed,
            exited = value.closed,
            errorMessage = value.error?.let { (it["message"] as? JsonPrimitive)?.contentOrNull
                ?: (it["code"] as? JsonPrimitive)?.contentOrNull ?: "Video processing failed. Retry extraction or choose another video." }
        )
        loadReviewFrame(value)
    }
    private fun loadReviewFrame(value: BackendSession) {
        val hash = (value.image?.get("sha256") as? JsonPrimitive)?.contentOrNull ?: return
        if (!hash.matches(Regex("[0-9a-f]{64}")) || !foreground || value.busy || saved.get<String>("frameHash") == hash) return
        if (frameJob?.isActive == true && requestedFrameHash == hash) return
        frameJob?.cancel()
        requestedFrameHash = hash
        val epoch = generation
        frameJob = viewModelScope.launch {
            try {
                val bytes = repository.getFrame(value.session_id)
                val path = videos.saveFrame("${value.session_id}-$hash", bytes)
                if (epoch != generation || session.value?.session_id != value.session_id ||
                    (session.value?.image?.get("sha256") as? JsonPrimitive)?.contentOrNull != hash) {
                    videos.remove(path)
                    return@launch
                }
                saved.get<String>("framePath")?.takeIf { it != path }?.let(videos::remove)
                saved["framePath"] = path; saved["frameHash"] = hash
                activeFrame = videos.preview(path)
                session.value?.let(::applySnapshot)
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (_: Exception) {
                if (epoch == generation) uiState.value = uiState.value.copy(errorMessage = "Could not load the selected review frame. Retry to refresh it.")
            }
        }
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
