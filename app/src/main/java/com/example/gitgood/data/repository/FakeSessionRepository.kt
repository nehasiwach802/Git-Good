package com.example.gitgood.data.repository

import com.example.gitgood.data.model.localExperiments
import com.example.gitgood.data.model.session.*
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

/**
 * Offline, single-client, in-memory demo. It never calls a server/model/Firebase.
 * No snapshot survives process death. Image links are non-resolving demo placeholders.
 * The caller/UI must display demoNotice; every generated assistant message is also labeled.
 */
class FakeSessionRepository(
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
    private val jobDelayMillis: Long = 700,
    private val scenario: Scenario = Scenario.NORMAL,
    private val unavailableExperimentIds: Set<String> = emptySet()
) : SessionRepository {
    enum class Scenario { NORMAL, EXTRACTION_FAILS_ONCE, REQUEST_CLEARER_IMAGE }
    override val demoNotice = DEMO_NOTICE
    private val mutex = Mutex()
    private data class Record(
        var snapshot: SessionSnapshot,
        var revision: Long = 0,
        var imageId: String? = null,
        var evidenceOffered: Boolean = false,
        var failedOnce: Boolean = false,
        var failedJobType: JobType? = null,
        var worker: Job? = null
    )
    private data class Replay(val fingerprint: String, val response: RepositoryResponse<SessionSnapshot>)
    private val sessions = mutableMapOf<String, Record>()
    private val replays = mutableMapOf<String, Replay>()

    override suspend fun getHealth() = SessionHealth()
    override suspend fun getExperiments() = RepositoryResponse(id(), ExperimentList(catalog()))

    override suspend fun createSession(request: CreateSessionRequest, idempotencyKey: String) = mutex.withLock {
        uuid(idempotencyKey)
        val key = "create:$idempotencyKey"
        val fingerprint = fingerprint(request.experimentId, request.experimentVersion)
        replay(key, fingerprint)?.let { return@withLock it }
        val experiment = catalog().find { it.id == request.experimentId }
            ?: fail(SessionErrorCode.NOT_FOUND, 404, "Experiment not found.")
        if (experiment.supportStatus != SupportStatus.AVAILABLE) fail(SessionErrorCode.EXPERIMENT_UNAVAILABLE, 409, "This demo experiment is unavailable.")
        if (experiment.version != request.experimentVersion) fail(SessionErrorCode.EXPERIMENT_VERSION_UNAVAILABLE, 409, "Choose the exact catalog version.")
        val timestamp = now()
        val snapshot = SessionSnapshot(
            id(), SessionMode.STUB, experiment.id, experiment.version, 1,
            SessionStatus.AWAITING_IMAGE, null, listOf(message("system", DEMO_NOTICE)),
            listOf(uploadAction()), null, null, timestamp, timestamp
        )
        sessions[snapshot.sessionId] = Record(snapshot)
        remember(key, fingerprint, response(snapshot, 201))
    }

    override suspend fun getSession(sessionId: String) = mutex.withLock {
        // Reads do not complete jobs, alter versions or append messages.
        response(record(sessionId).snapshot)
    }

    override suspend fun uploadImage(
        sessionId: String, expectedSessionVersion: Long, image: SessionImage,
        description: String, idempotencyKey: String
    ) = mutex.withLock {
        uuid(idempotencyKey)
        val bytes = image.bytes.copyOf()
        val descriptionText = description.trim()
        val sha = sha256(bytes)
        val key = "image:$sessionId:$idempotencyKey"
        val fingerprint = fingerprint(expectedSessionVersion.toString(), descriptionText, sha, image.contentType)
        replay(key, fingerprint)?.let { return@withLock it }
        val record = record(sessionId)
        checkMutable(record, expectedSessionVersion)
        text(descriptionText, 2000, "description")
        if (bytes.size > 5 * 1024 * 1024) fail(SessionErrorCode.IMAGE_TOO_LARGE, 413, "Images must be at most 5 MiB.")
        val (width, height) = imageDimensions(bytes, image.contentType)
        val receipt = SessionImageReceipt(id(), image.contentType, bytes.size.toLong(), width, height, sha)
        val attachment = MessageAttachment(image = receipt, url = "https://demo.invalid/images/${receipt.imageId}", urlExpiresAt = now(15 * 60 * 1000L))
        record.imageId = receipt.imageId
        record.evidenceOffered = false
        record.failedJobType = null
        record.snapshot = record.snapshot.copy(
            candidate = null, assessment = null, pendingActions = emptyList(),
            messages = record.snapshot.messages + message("user", descriptionText, listOf(attachment))
        )
        queue(record, JobType.EXTRACTION)
        remember(key, fingerprint, response(record.snapshot, 202))
    }

    override suspend fun submitEvent(sessionId: String, event: SessionEvent) = mutex.withLock {
        uuid(event.eventId)
        val key = "event:$sessionId:${event.eventId}"
        val fingerprint = eventFingerprint(event)
        replay(key, fingerprint)?.let { return@withLock it }
        val record = record(sessionId)
        if (event.expectedSessionVersion < 1 || (revision(event)?.let { it < 1 } == true)) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Versions must be positive.")
        if (event is CloseSessionEvent && event.payload.reason != "user_exit") fail(SessionErrorCode.VALIDATION_ERROR, 422, "Invalid close reason.")
        if (event is CloseSessionEvent && record.snapshot.status == SessionStatus.CLOSED) {
            return@withLock remember(key, fingerprint, response(record.snapshot))
        }
        checkMutable(record, event.expectedSessionVersion, revision(event), event is CloseSessionEvent)
        var status = 200
        when (event) {
            is MessageEvent -> {
                text(event.payload.text, 4000, "text")
                append(record, "user", event.payload.text)
                queue(record, JobType.REPLY)
                status = 202
            }
            is ConfirmCandidateEvent -> {
                action<ConfirmRevisionAction>(record, event.payload.actionId)
                record.snapshot = record.snapshot.copy(candidate = record.snapshot.candidate!!.copy(confirmed = true), pendingActions = emptyList())
                append(record, "user", "Confirmed candidate revision ${event.candidateRevision}.")
                queue(record, JobType.ANALYSIS)
                status = 202
            }
            is SubmitCorrectionEvent -> correct(record, event)
            is SubmitMeasurementEvent -> {
                val action = action<EnterMeasurementAction>(record, event.payload.actionId)
                val p = event.payload
                if (p.measurementId != action.measurementId || p.unit != action.unit || !p.value.isFinite() ||
                    (action.minimum != null && p.value < action.minimum) || (action.maximum != null && p.value > action.maximum)) {
                    fail(SessionErrorCode.VALIDATION_ERROR, 422, "Use the requested measurement ID, unit and allowed range.")
                }
                consume(record, action.actionId)
                append(record, "user", "Measurement ${p.measurementId}: ${p.value} ${p.unit} (user-reported).")
                queue(record, JobType.ANALYSIS)
                status = 202
            }
            is SubmitCheckResultEvent -> {
                val action = action<PerformCheckAction>(record, event.payload.actionId)
                val p = event.payload
                if (p.checkId != action.checkId || p.result !in listOf("passed", "failed", "inconclusive") || p.observation.codePointCount(0, p.observation.length) > 2000) {
                    fail(SessionErrorCode.VALIDATION_ERROR, 422, "Invalid check ID, result or observation.")
                }
                consume(record, action.actionId)
                append(record, "user", "Check ${p.checkId}: ${p.result}. ${p.observation.orEmpty()} (user-reported).")
                queue(record, JobType.ANALYSIS)
                status = 202
            }
            is RequestInstructorHelpEvent -> fail(SessionErrorCode.ACTION_UNAVAILABLE, 409, "Demo mode cannot contact an instructor.")
            is RetryJobEvent -> {
                val action = action<RetryJobAction>(record, event.payload.actionId)
                if (action.failedJobId != event.payload.failedJobId || record.failedJobType == null) {
                    fail(SessionErrorCode.ACTION_UNAVAILABLE, 409, "This job cannot be retried.", record.snapshot)
                }
                val type = record.failedJobType!!
                record.snapshot = record.snapshot.copy(pendingActions = emptyList())
                queue(record, type)
                status = 202
            }
            is CloseSessionEvent -> {
                if (event.payload.reason != "user_exit") fail(SessionErrorCode.VALIDATION_ERROR, 422, "Invalid close reason.")
                record.worker?.cancel()
                append(record, "system", "[DEMO] Conversation closed locally. No server was contacted.")
                record.snapshot = record.snapshot.copy(status = SessionStatus.CLOSED, pendingActions = emptyList(), job = null)
                bump(record)
            }
        }
        remember(key, fingerprint, response(record.snapshot, status))
    }

    private fun correct(record: Record, event: SubmitCorrectionEvent) {
        action<ReviewConnectionAction>(record, event.payload.actionId)
        val candidate = record.snapshot.candidate!!
        val changes = event.payload.connectionChanges
        if (changes.isEmpty() || changes.size > 50 || event.payload.note.codePointCount(0, event.payload.note.length) > 2000) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Supply 1-50 connection changes and a short note.")
        // Work on a local copy: any invalid operation leaves domain state untouched.
        val connections = candidate.connections.toMutableList()
        fun endpoint(e: CircuitEndpoint) {
            if (candidate.components.none { it.id == e.componentId && e.pin in it.pins }) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Unknown component or pin.")
        }
        changes.forEach { change ->
            when (change) {
                is AddConnection -> {
                    endpoint(change.from); endpoint(change.to)
                    connections.add(CircuitConnection(id(), change.from, change.to))
                }
                is RemoveConnection -> if (!connections.removeAll { it.id == change.connectionId }) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Unknown connection.")
                is ReplaceConnection -> {
                    endpoint(change.from); endpoint(change.to)
                    val index = connections.indexOfFirst { it.id == change.connectionId }
                    if (index < 0) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Unknown connection.")
                    connections[index] = CircuitConnection(change.connectionId, change.from, change.to)
                }
            }
        }
        record.revision++
        record.evidenceOffered = false
        val updated = candidate.copy(revision = record.revision, connections = connections.toList(), confirmed = false)
        record.snapshot = record.snapshot.copy(candidate = updated, assessment = null, pendingActions = reviewActions(updated), status = SessionStatus.AWAITING_INPUT)
        append(record, "user", "Submitted wiring correction. ${event.payload.note.orEmpty()}")
        append(record, "assistant", "[DEMO] Synthetic revision ${updated.revision} needs review and confirmation. No wiring was analyzed.")
        bump(record)
    }

    private fun queue(record: Record, type: JobType) {
        val job = SessionJob(id(), type)
        record.snapshot = record.snapshot.copy(job = job, status = if (type == JobType.EXTRACTION) SessionStatus.EXTRACTING else SessionStatus.ANALYZING)
        bump(record)
        val sessionId = record.snapshot.sessionId
        record.worker = scope.launch {
            delay(jobDelayMillis)
            mutex.withLock {
                val current = sessions[sessionId] ?: return@withLock
                if (!isCurrent(current, job.jobId)) return@withLock
                current.snapshot = current.snapshot.copy(job = job.copy(status = JobStatus.RUNNING))
                bump(current)
            }
            delay(jobDelayMillis)
            mutex.withLock {
                val current = sessions[sessionId] ?: return@withLock
                if (isCurrent(current, job.jobId)) complete(current, job)
            }
        }
    }

    private fun complete(record: Record, job: SessionJob) {
        if (job.type == JobType.EXTRACTION && scenario == Scenario.EXTRACTION_FAILS_ONCE && !record.failedOnce) {
            record.failedOnce = true
            record.failedJobType = job.type
            record.snapshot = record.snapshot.copy(status = SessionStatus.FAILED, job = null, pendingActions = listOf(
                RetryJobAction(id(), "Retry demo job", failedJobId = job.jobId, reason = "Simulated extraction failure")
            ))
            append(record, "assistant", "[DEMO] Simulated extraction failure. Retry runs another fake job.")
        } else {
            when (job.type) {
                JobType.EXTRACTION -> {
                    if (scenario == Scenario.REQUEST_CLEARER_IMAGE) {
                        record.snapshot = record.snapshot.copy(candidate = null, pendingActions = listOf(uploadAction()))
                        append(record, "assistant", "[DEMO] Simulated unclear-image scenario. Supply another image; no extraction occurred.")
                    } else {
                        record.revision++
                        val sample = CircuitCandidate(record.revision, record.imageId!!,
                            listOf(CircuitComponent("r1", "resistor", "Demo R1", "1000 ohm", listOf("1", "2")), CircuitComponent("gnd", "ground", "Demo ground", null, listOf("0"))),
                            listOf(CircuitConnection("wire-1", CircuitEndpoint("r1", "2"), CircuitEndpoint("gnd", "0"))))
                        record.snapshot = record.snapshot.copy(candidate = sample, pendingActions = reviewActions(sample))
                        append(record, "assistant", "[DEMO] This is synthetic sample wiring for testing the review flow, not wiring extracted from your image.")
                    }
                }
                JobType.ANALYSIS -> {
                    val candidate = record.snapshot.candidate
                    if (!record.evidenceOffered && candidate?.confirmed == true) {
                        record.evidenceOffered = true
                        record.snapshot = record.snapshot.copy(pendingActions = listOf(
                            EnterMeasurementAction(id(), "Enter demo measurement", candidate.revision, "demo-voltage", "[DEMO] Enter a sample voltage; do not energize a circuit for this simulation.", "voltage", "V", null, null, emptyList()),
                            PerformCheckAction(id(), "Record demo check", candidate.revision, "demo-review", "[DEMO] Record a sample visual-review result. This does not validate the circuit.")
                        ))
                    }
                    append(record, "assistant", "[DEMO] Evidence recorded in the simulated workflow. No model ran and circuit correctness is unknown.")
                }
                JobType.REPLY -> append(record, "assistant", "[DEMO] Simulated follow-up reply. I cannot assess or diagnose this circuit; use the structured demo actions to test the workflow.")
            }
            record.failedJobType = null
            record.snapshot = record.snapshot.copy(job = null, status = if (record.snapshot.pendingActions.isEmpty()) SessionStatus.READY else SessionStatus.AWAITING_INPUT)
        }
        // Invariant: a stub session never carries a correctness assessment.
        record.snapshot = record.snapshot.copy(assessment = null)
        bump(record)
    }

    private fun checkMutable(record: Record, expected: Long, revision: Long? = null, allowBusy: Boolean = false) {
        val s = record.snapshot
        if (expected < 1 || (revision != null && revision < 1)) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Versions must be positive.")
        if (s.status == SessionStatus.CLOSED) fail(SessionErrorCode.SESSION_CLOSED, 409, "Conversation is closed.", s)
        if (revision != null && s.candidate?.revision != revision) fail(SessionErrorCode.STALE_CANDIDATE, 409, "Wiring changed. Review the current revision.", s)
        if (s.sessionVersion != expected) fail(SessionErrorCode.STALE_SESSION, 409, "Refresh the latest session before submitting.", s)
        if (!allowBusy && s.job != null) throw SessionRepositoryException(SessionErrorCode.JOB_IN_PROGRESS, 409, "Wait for the current demo job.", s, retryable = true)
    }
    private inline fun <reified T : SessionAction> action(record: Record, id: String): T =
        record.snapshot.pendingActions.find { it.actionId == id } as? T
            ?: fail(SessionErrorCode.ACTION_UNAVAILABLE, 409, "This action is no longer pending.", record.snapshot)
    private fun consume(record: Record, id: String) { record.snapshot = record.snapshot.copy(pendingActions = record.snapshot.pendingActions.filterNot { it.actionId == id }) }
    private fun reviewActions(candidate: CircuitCandidate): List<SessionAction> = buildList {
        candidate.connections.forEach { add(ReviewConnectionAction(id(), "Review demo connection", candidate.revision, it.id, "[DEMO] Review this synthetic connection.")) }
        add(ConfirmRevisionAction(id(), "Confirm demo revision", candidate.revision, "[DEMO] Confirm this exact synthetic revision."))
    }
    private fun uploadAction() = UploadImageAction(id(), "Choose demo image", prompt = "[DEMO] Add JPEG/PNG and a description. The image is not analyzed.")
    private fun catalog() = localExperiments.map {
        SessionExperiment(it.id, it.name, it.version, it.description,
            if (it.id in unavailableExperimentIds) SupportStatus.UNAVAILABLE else SupportStatus.AVAILABLE,
            DEMO_NOTICE, ExperimentCapabilities(false, true, true, false))
    }
    private fun isCurrent(record: Record, jobId: String) = record.snapshot.status != SessionStatus.CLOSED && record.snapshot.job?.jobId == jobId
    private fun record(id: String) = sessions[id] ?: fail(SessionErrorCode.NOT_FOUND, 404, "Demo session not found. In-memory state is lost after app restart.")
    private fun response(s: SessionSnapshot, status: Int = 200) = RepositoryResponse(id(), s, status)
    private fun replay(key: String, fingerprint: String): RepositoryResponse<SessionSnapshot>? {
        val saved = replays[key] ?: return null
        if (saved.fingerprint != fingerprint) fail(SessionErrorCode.IDEMPOTENCY_CONFLICT, 409, "This retry ID was already used with different input.")
        return saved.response.copy(replayed = true)
    }
    private fun remember(key: String, fingerprint: String, response: RepositoryResponse<SessionSnapshot>): RepositoryResponse<SessionSnapshot> {
        replays[key] = Replay(fingerprint, response)
        return response
    }
    private fun bump(record: Record) { record.snapshot = record.snapshot.copy(sessionVersion = record.snapshot.sessionVersion + 1, updatedAt = now()) }
    private fun append(record: Record, role: String, text: String) { record.snapshot = record.snapshot.copy(messages = record.snapshot.messages + message(role, text)) }
    private fun message(role: String, text: String, attachments: List<MessageAttachment> = emptyList()) = SessionMessage(id(), role, text, attachments, now())
    private fun id() = UUID.randomUUID().toString()
    private fun now(offset: Long = 0) = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date(System.currentTimeMillis() + offset))
    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun fingerprint(vararg parts: String) = sha256(parts.joinToString("") { "${it.toByteArray(Charsets.UTF_8).size}:$it" }.toByteArray(Charsets.UTF_8))
    private fun text(value: String, limit: Int, field: String) {
        if (value.isBlank() || value.codePointCount(0, value.length) > limit) throw SessionRepositoryException(SessionErrorCode.VALIDATION_ERROR, 422, "Invalid $field.", fieldErrors = listOf(SessionFieldError(field, "Required, maximum $limit characters.")))
    }
    private fun uuid(value: String) {
        if (runCatching { UUID.fromString(value).toString().equals(value, ignoreCase = true) }.getOrDefault(false).not()) fail(SessionErrorCode.VALIDATION_ERROR, 422, "Request/event IDs must be UUIDs.")
    }
    private fun revision(e: SessionEvent): Long? = when (e) {
        is ConfirmCandidateEvent -> e.candidateRevision
        is SubmitCorrectionEvent -> e.candidateRevision
        is SubmitMeasurementEvent -> e.candidateRevision
        is SubmitCheckResultEvent -> e.candidateRevision
        else -> null
    }
    private fun eventFingerprint(e: SessionEvent): String {
        val parts = mutableListOf(e::class.java.simpleName, e.expectedSessionVersion.toString(), revision(e).toString())
        fun endpoint(p: CircuitEndpoint) { parts.add(p.componentId); parts.add(p.pin) }
        when (e) {
            is MessageEvent -> parts.add(e.payload.text)
            is ConfirmCandidateEvent -> parts.add(e.payload.actionId)
            is SubmitCorrectionEvent -> {
                parts.add(e.payload.actionId); parts.add(e.payload.note.orEmpty())
                e.payload.connectionChanges.forEach {
                    when (it) {
                        is AddConnection -> { parts.add("add"); endpoint(it.from); endpoint(it.to) }
                        is RemoveConnection -> { parts.add("remove"); parts.add(it.connectionId) }
                        is ReplaceConnection -> { parts.add("replace"); parts.add(it.connectionId); endpoint(it.from); endpoint(it.to) }
                    }
                }
            }
            is SubmitMeasurementEvent -> parts.addAll(listOf(e.payload.actionId, e.payload.measurementId, e.payload.value.toString(), e.payload.unit))
            is SubmitCheckResultEvent -> parts.addAll(listOf(e.payload.actionId, e.payload.checkId, e.payload.result, e.payload.observation.orEmpty()))
            is RequestInstructorHelpEvent -> parts.addAll(listOf(e.payload.actionId, e.payload.reason))
            is RetryJobEvent -> parts.addAll(listOf(e.payload.actionId, e.payload.failedJobId))
            is CloseSessionEvent -> parts.add(e.payload.reason)
        }
        return fingerprint(*parts.toTypedArray())
    }
    private fun imageDimensions(bytes: ByteArray, mime: String): Pair<Int, Int> {
        fun bad(): Nothing = fail(SessionErrorCode.UNSUPPORTED_IMAGE, 415, "Use a JPEG/PNG with a readable image header.")
        if (mime == "image/png" && bytes.size >= 24 && bytes.copyOfRange(0, 8).contentEquals(byteArrayOf(-119, 80, 78, 71, 13, 10, 26, 10)) && String(bytes, 12, 4, Charsets.US_ASCII) == "IHDR") {
            val w = ByteBuffer.wrap(bytes, 16, 4).int; val h = ByteBuffer.wrap(bytes, 20, 4).int
            if (w > 0 && h > 0) return w to h
        }
        if (mime == "image/jpeg" && bytes.size > 4 && bytes[0] == (-1).toByte() && bytes[1] == (-40).toByte()) {
            var i = 2
            fun u(index: Int) = bytes[index].toInt() and 255
            while (i + 3 < bytes.size) {
                if (u(i) != 255) bad()
                while (i < bytes.size && u(i) == 255) i++
                if (i >= bytes.size) bad()
                val marker = u(i++)
                if (marker == 0xDA || marker == 0xD9) break
                if (marker == 0x01 || marker in 0xD0..0xD8) continue
                if (i + 1 >= bytes.size) bad()
                val length = (u(i) shl 8) + u(i + 1)
                if (length < 2 || i + length > bytes.size) bad()
                if (marker in 0xC0..0xCF && marker !in listOf(0xC4, 0xC8, 0xCC) && length >= 8) {
                    val h = (u(i + 3) shl 8) + u(i + 4); val w = (u(i + 5) shl 8) + u(i + 6)
                    if (w > 0 && h > 0) return w to h
                    bad()
                }
                i += length
            }
        }
        bad()
    }
    private fun fail(code: SessionErrorCode, status: Int, message: String, current: SessionSnapshot? = null): Nothing = throw SessionRepositoryException(code, status, message, current)
}
