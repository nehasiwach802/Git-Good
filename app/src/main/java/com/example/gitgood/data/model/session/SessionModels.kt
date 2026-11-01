package com.example.gitgood.data.model.session

import kotlinx.serialization.Transient
import java.util.UUID
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.JsonClassDiscriminator

const val DEMO_NOTICE = "DEMO MODE: simulated responses only. No image extraction, circuit diagnosis, or instructor contact is performed."

/** HTTP metadata is separate from the JSON response envelope. */
@Serializable
data class RepositoryResponse<T>(
    @SerialName("request_id") val requestId: String, val data: T,
    @Transient val httpStatus: Int = 200, @Transient val replayed: Boolean = false
)

@Serializable
enum class SessionMode { @SerialName("stub") STUB, @SerialName("live") LIVE }
@Serializable
enum class SessionStatus {
    @SerialName("awaiting_image") AWAITING_IMAGE, @SerialName("extracting") EXTRACTING,
    @SerialName("awaiting_input") AWAITING_INPUT, @SerialName("analyzing") ANALYZING,
    @SerialName("ready") READY, @SerialName("failed") FAILED, @SerialName("closed") CLOSED
}
@Serializable
enum class SupportStatus { @SerialName("available") AVAILABLE, @SerialName("coming_soon") COMING_SOON, @SerialName("unavailable") UNAVAILABLE }
@Serializable
data class ExperimentCapabilities(
    @SerialName("image_analysis") val imageAnalysis: Boolean,
    @SerialName("follow_up_images") val followUpImages: Boolean,
    val measurements: Boolean,
    @SerialName("instructor_help") val instructorHelp: Boolean
)
@Serializable
data class SessionExperiment(
    val id: String, val name: String, val version: String, val description: String,
    @SerialName("support_status") val supportStatus: SupportStatus,
    @SerialName("support_reason") val supportReason: String?, val capabilities: ExperimentCapabilities
)
@Serializable
data class ExperimentList(val experiments: List<SessionExperiment>)
@Serializable
data class SessionHealth(val status: String = "ok", val service: String = "circuitly-api", @SerialName("api_version") val apiVersion: String = "1", val mode: SessionMode = SessionMode.STUB)
@Serializable
data class CreateSessionRequest(@SerialName("experiment_id") val experimentId: String, @SerialName("experiment_version") val experimentVersion: String)

/** Binary multipart input, not JSON. Byte content is copied by the fake at submission. */
data class SessionImage(val bytes: ByteArray, val contentType: String)
@Serializable
data class SessionImageReceipt(
    @SerialName("image_id") val imageId: String,
    @SerialName("content_type") val contentType: String,
    @SerialName("size_bytes") val sizeBytes: Long,
    val width: Int, val height: Int, val sha256: String
)
@Serializable
data class MessageAttachment(
    val type: String = "image", val image: SessionImageReceipt,
    val url: String, @SerialName("url_expires_at") val urlExpiresAt: String
)
@Serializable
data class SessionMessage(
    @SerialName("message_id") val messageId: String, val role: String, val text: String,
    val attachments: List<MessageAttachment> = emptyList(), @SerialName("created_at") val createdAt: String
)
@Serializable
data class CircuitEndpoint(@SerialName("component_id") val componentId: String, val pin: String)
@Serializable
data class CircuitComponent(val id: String, val type: String, val label: String, val value: String?, val pins: List<String>)
@Serializable
data class CircuitConnection(val id: String, val from: CircuitEndpoint, val to: CircuitEndpoint)
@Serializable
data class CircuitCandidate(val revision: Long, @SerialName("image_id") val imageId: String, val components: List<CircuitComponent>, val connections: List<CircuitConnection>, val confirmed: Boolean = false)
@Serializable
enum class JobType { @SerialName("extraction") EXTRACTION, @SerialName("analysis") ANALYSIS, @SerialName("reply") REPLY }
@Serializable
enum class JobStatus { @SerialName("queued") QUEUED, @SerialName("running") RUNNING }
@Serializable
data class SessionJob(@SerialName("job_id") val jobId: String, val type: JobType, val status: JobStatus = JobStatus.QUEUED, @SerialName("retry_after_ms") val retryAfterMs: Int = 2000)
@Serializable
data class AssessmentFinding(val code: String, val severity: String, val message: String, @SerialName("component_ids") val componentIds: List<String>, @SerialName("connection_ids") val connectionIds: List<String>)
@Serializable
data class SessionAssessment(@SerialName("candidate_revision") val candidateRevision: Long, val verdict: String, val explanation: String, val findings: List<AssessmentFinding>, @SerialName("created_at") val createdAt: String)

@Serializable
sealed interface SessionAction {
    val actionId: String
    val label: String
    val candidateRevision: Long?
}

@Serializable @SerialName("upload_image")
data class UploadImageAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long? = null,
    val prompt: String, @SerialName("accepted_content_types") val acceptedContentTypes: List<String> = listOf("image/jpeg", "image/png"), @SerialName("max_size_bytes") val maxSizeBytes: Int = 5 * 1024 * 1024, @SerialName("description_required") val descriptionRequired: Boolean = true
) : SessionAction

@Serializable @SerialName("review_connection")
data class ReviewConnectionAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long,
    @SerialName("connection_id") val connectionId: String, val prompt: String
) : SessionAction

@Serializable @SerialName("confirm_revision")
data class ConfirmRevisionAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long,
    val prompt: String
) : SessionAction

@Serializable @SerialName("enter_measurement")
data class EnterMeasurementAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long,
    @SerialName("measurement_id") val measurementId: String, val prompt: String, val quantity: String, val unit: String, val minimum: Double?, val maximum: Double?, @SerialName("probe_points") val probePoints: List<CircuitEndpoint>
) : SessionAction

@Serializable @SerialName("perform_check")
data class PerformCheckAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long,
    @SerialName("check_id") val checkId: String, val instructions: String
) : SessionAction

@Serializable @SerialName("request_instructor_help")
data class RequestInstructorHelpAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long? = null,
    val reason: String
) : SessionAction

@Serializable @SerialName("retry_job")
data class RetryJobAction(
    @SerialName("action_id") override val actionId: String, override val label: String,
    @SerialName("candidate_revision") override val candidateRevision: Long? = null,
    @SerialName("failed_job_id") val failedJobId: String, val reason: String
) : SessionAction

@Serializable
data class SessionSnapshot(
    @SerialName("session_id") val sessionId: String, val mode: SessionMode,
    @SerialName("experiment_id") val experimentId: String,
    @SerialName("experiment_version") val experimentVersion: String,
    @SerialName("session_version") val sessionVersion: Long,
    val status: SessionStatus, val candidate: CircuitCandidate?, val messages: List<SessionMessage>,
    @SerialName("pending_actions") val pendingActions: List<SessionAction>, val job: SessionJob?,
    val assessment: SessionAssessment?, @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String
)

@Serializable
data class MessagePayload(val text: String)
@Serializable
data class ConfirmPayload(@SerialName("action_id") val actionId: String)
@Serializable
data class MeasurementPayload(@SerialName("action_id") val actionId: String, @SerialName("measurement_id") val measurementId: String, val value: Double, val unit: String)
@Serializable
data class CheckPayload(@SerialName("action_id") val actionId: String, @SerialName("check_id") val checkId: String, val result: String, val observation: String = "")
@Serializable
data class CorrectionPayload(@SerialName("action_id") val actionId: String, @SerialName("connection_changes") val connectionChanges: List<ConnectionChange>, val note: String = "")
@OptIn(ExperimentalSerializationApi::class)
@JsonClassDiscriminator("operation")
@Serializable
sealed interface ConnectionChange
@Serializable @SerialName("add")
data class AddConnection(val from: CircuitEndpoint, val to: CircuitEndpoint) : ConnectionChange
@Serializable @SerialName("remove")
data class RemoveConnection(@SerialName("connection_id") val connectionId: String) : ConnectionChange
@Serializable @SerialName("replace")
data class ReplaceConnection(@SerialName("connection_id") val connectionId: String, val from: CircuitEndpoint, val to: CircuitEndpoint) : ConnectionChange
@Serializable
data class InstructorPayload(@SerialName("action_id") val actionId: String, val reason: String)
@Serializable
data class RetryJobPayload(@SerialName("action_id") val actionId: String, @SerialName("failed_job_id") val failedJobId: String)
@Serializable
data class ClosePayload(val reason: String = "user_exit")

@Serializable
sealed interface SessionEvent {
    val eventId: String
    val expectedSessionVersion: Long
}

@Serializable @SerialName("message")
data class MessageEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    val payload: MessagePayload
) : SessionEvent

@Serializable @SerialName("confirm_candidate")
data class ConfirmCandidateEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    @SerialName("candidate_revision") val candidateRevision: Long, val payload: ConfirmPayload
) : SessionEvent

@Serializable @SerialName("submit_correction")
data class SubmitCorrectionEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    @SerialName("candidate_revision") val candidateRevision: Long, val payload: CorrectionPayload
) : SessionEvent

@Serializable @SerialName("submit_measurement")
data class SubmitMeasurementEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    @SerialName("candidate_revision") val candidateRevision: Long, val payload: MeasurementPayload
) : SessionEvent

@Serializable @SerialName("submit_check_result")
data class SubmitCheckResultEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    @SerialName("candidate_revision") val candidateRevision: Long, val payload: CheckPayload
) : SessionEvent

@Serializable @SerialName("request_instructor_help")
data class RequestInstructorHelpEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    val payload: InstructorPayload
) : SessionEvent

@Serializable @SerialName("retry_job")
data class RetryJobEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    val payload: RetryJobPayload
) : SessionEvent

@Serializable @SerialName("close_session")
data class CloseSessionEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("expected_session_version") override val expectedSessionVersion: Long,
    val payload: ClosePayload
) : SessionEvent

@Serializable
enum class SessionErrorCode {
    NOT_FOUND, EXPERIMENT_UNAVAILABLE, EXPERIMENT_VERSION_UNAVAILABLE, STALE_SESSION,
    STALE_CANDIDATE, ACTION_UNAVAILABLE, SESSION_CLOSED, JOB_IN_PROGRESS,
    IDEMPOTENCY_CONFLICT, IMAGE_TOO_LARGE, UNSUPPORTED_IMAGE, VALIDATION_ERROR
}
@Serializable
data class SessionFieldError(val field: String, val message: String)
@Serializable
data class SessionApiError(
    val code: SessionErrorCode, val message: String, val retryable: Boolean,
    @SerialName("field_errors") val fieldErrors: List<SessionFieldError>,
    @SerialName("current_session") val currentSession: SessionSnapshot?
)
@Serializable
data class SessionErrorResponse(@SerialName("request_id") val requestId: String, val error: SessionApiError)
class SessionRepositoryException(
    val code: SessionErrorCode, val httpStatus: Int, message: String,
    val currentSession: SessionSnapshot? = null, val retryable: Boolean = false,
    val fieldErrors: List<SessionFieldError> = emptyList()
) : Exception(message) {
    val requestId: String = UUID.randomUUID().toString()
    fun toResponse() = SessionErrorResponse(requestId, SessionApiError(code, message.orEmpty(), retryable, fieldErrors, currentSession))
}
