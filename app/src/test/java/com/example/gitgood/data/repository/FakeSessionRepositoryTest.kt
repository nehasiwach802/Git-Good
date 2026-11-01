package com.example.gitgood.data.repository

import com.example.gitgood.data.model.session.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test
import java.util.Base64
import java.util.UUID

@OptIn(ExperimentalCoroutinesApi::class)
class FakeSessionRepositoryTest {
    private fun id() = UUID.randomUUID().toString()
    private fun image() = SessionImage(Base64.getDecoder().decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII="), "image/png")
    private suspend fun create(repo: SessionRepository) = repo.createSession(CreateSessionRequest("ohms-law", "1"), id()).data
    private suspend fun upload(repo: SessionRepository, s: SessionSnapshot) = repo.uploadImage(s.sessionId, s.sessionVersion, image(), "A demo circuit", id()).data
    private suspend fun error(code: SessionErrorCode, block: suspend () -> Unit): SessionRepositoryException {
        try { block() } catch (e: SessionRepositoryException) { assertEquals(code, e.code); return e }
        throw AssertionError("Expected $code")
    }

    @Test fun catalogAndSnapshotsAreExplicitlyDemo() = runTest {
        val repo = FakeSessionRepository(this)
        assertTrue(repo.demoNotice.contains("DEMO MODE"))
        assertEquals(5, repo.getExperiments().data.experiments.size)
        assertTrue(repo.getExperiments().data.experiments.all { !it.capabilities.imageAnalysis && !it.capabilities.instructorHelp })
        val s = create(repo)
        assertEquals(SessionMode.STUB, s.mode)
        assertNull(s.assessment)
        assertTrue(s.messages.first().text.contains("DEMO MODE"))
        assertTrue(s.pendingActions.single() is UploadImageAction)
    }
    @Test fun duplicateCreateReturnsSameSessionAndOriginalRequestId() = runTest {
        val repo = FakeSessionRepository(this); val key = id(); val request = CreateSessionRequest("ohms-law", "1")
        val first = repo.createSession(request, key); val replay = repo.createSession(request, key)
        assertEquals(first.data, replay.data); assertEquals(first.requestId, replay.requestId); assertTrue(replay.replayed)
        error(SessionErrorCode.IDEMPOTENCY_CONFLICT) { repo.createSession(request.copy(experimentId = "rc-low-pass-filter"), key) }
    }
    @Test fun getDoesNotChangeVersionOrFinishQueuedJob() = runTest {
        val repo = FakeSessionRepository(this); val s = upload(repo, create(repo))
        repeat(3) { assertEquals(s, repo.getSession(s.sessionId).data) }
        advanceUntilIdle()
        assertEquals(SessionStatus.AWAITING_INPUT, repo.getSession(s.sessionId).data.status)
    }
    @Test fun uploadReplayIsCheckedBeforeStaleVersionAndDoesNotAddAnotherMessage() = runTest {
        val repo = FakeSessionRepository(this); val s = create(repo); val key = id()
        val first = repo.uploadImage(s.sessionId, s.sessionVersion, image(), "Circuit", key)
        advanceUntilIdle()
        val current = repo.getSession(s.sessionId).data
        val replay = repo.uploadImage(s.sessionId, s.sessionVersion, image(), "Circuit", key)
        assertTrue(replay.replayed); assertEquals(first.data, replay.data)
        assertEquals(current, repo.getSession(s.sessionId).data)
    }
    @Test fun staleConfirmationCannotConfirmNewWiring() = runTest {
        val repo = FakeSessionRepository(this); val submitted = upload(repo, create(repo)); advanceUntilIdle()
        val s = repo.getSession(submitted.sessionId).data
        val oldConfirm = s.pendingActions.filterIsInstance<ConfirmRevisionAction>().single()
        val review = s.pendingActions.filterIsInstance<ReviewConnectionAction>().first()
        val corrected = repo.submitEvent(s.sessionId, SubmitCorrectionEvent(id(), s.sessionVersion, s.candidate!!.revision,
            CorrectionPayload(review.actionId, listOf(ReplaceConnection("wire-1", CircuitEndpoint("r1", "1"), CircuitEndpoint("gnd", "0")))))).data
        val failure = error(SessionErrorCode.STALE_CANDIDATE) {
            repo.submitEvent(s.sessionId, ConfirmCandidateEvent(id(), corrected.sessionVersion, s.candidate.revision, ConfirmPayload(oldConfirm.actionId)))
        }
        assertEquals(corrected, failure.currentSession)
        assertFalse(repo.getSession(s.sessionId).data.candidate!!.confirmed)
    }
    @Test fun staleSessionDoesNotAppendMessage() = runTest {
        val repo = FakeSessionRepository(this); val s = create(repo)
        error(SessionErrorCode.STALE_SESSION) { repo.submitEvent(s.sessionId, MessageEvent(id(), 99, MessagePayload("Hello"))) }
        assertEquals(s, repo.getSession(s.sessionId).data)
    }
    @Test fun eventReplayDoesNotQueueAnotherJob() = runTest {
        val repo = FakeSessionRepository(this); val s = create(repo)
        val e = MessageEvent(id(), s.sessionVersion, MessagePayload("How does this work?"))
        val first = repo.submitEvent(s.sessionId, e); advanceUntilIdle()
        val current = repo.getSession(s.sessionId).data
        assertEquals(first.data, repo.submitEvent(s.sessionId, e).data)
        assertEquals(current, repo.getSession(s.sessionId).data)
        error(SessionErrorCode.IDEMPOTENCY_CONFLICT) { repo.submitEvent(s.sessionId, e.copy(payload = MessagePayload("Different"))) }
    }
    @Test fun closingDuringJobPreventsLateResults() = runTest {
        val repo = FakeSessionRepository(this); val pending = upload(repo, create(repo))
        val closed = repo.submitEvent(pending.sessionId, CloseSessionEvent(id(), pending.sessionVersion, ClosePayload())).data
        advanceUntilIdle()
        assertEquals(closed, repo.getSession(closed.sessionId).data)
        assertEquals(SessionStatus.CLOSED, closed.status); assertNull(closed.job); assertTrue(closed.pendingActions.isEmpty())
        error(SessionErrorCode.SESSION_CLOSED) { repo.submitEvent(closed.sessionId, MessageEvent(id(), closed.sessionVersion, MessagePayload("Hello"))) }
        assertEquals(closed, repo.submitEvent(closed.sessionId, CloseSessionEvent(id(), 1, ClosePayload())).data)
    }
    @Test fun invalidCorrectionIsAtomic() = runTest {
        val repo = FakeSessionRepository(this); val pending = upload(repo, create(repo)); advanceUntilIdle()
        val s = repo.getSession(pending.sessionId).data; val action = s.pendingActions.filterIsInstance<ReviewConnectionAction>().first()
        error(SessionErrorCode.VALIDATION_ERROR) {
            repo.submitEvent(s.sessionId, SubmitCorrectionEvent(id(), s.sessionVersion, s.candidate!!.revision,
                CorrectionPayload(action.actionId, listOf(RemoveConnection("wire-1"), RemoveConnection("unknown")))))
        }
        assertEquals(s, repo.getSession(s.sessionId).data)
    }
    @Test fun newImageInvalidatesCandidateAndRevisionNeverReusesNumber() = runTest {
        val repo = FakeSessionRepository(this); val pending = upload(repo, create(repo)); advanceUntilIdle()
        val first = repo.getSession(pending.sessionId).data
        val next = upload(repo, first)
        assertNull(next.candidate); assertTrue(next.pendingActions.isEmpty()); assertNull(next.assessment)
        advanceUntilIdle()
        assertTrue(repo.getSession(next.sessionId).data.candidate!!.revision > first.candidate!!.revision)
    }
    @Test fun simulatedFailureCanBeRetriedWithoutReuploading() = runTest {
        val repo = FakeSessionRepository(this, scenario = FakeSessionRepository.Scenario.EXTRACTION_FAILS_ONCE)
        val pending = upload(repo, create(repo)); advanceUntilIdle()
        val failed = repo.getSession(pending.sessionId).data
        assertEquals(SessionStatus.FAILED, failed.status)
        val action = failed.pendingActions.single() as RetryJobAction
        repo.submitEvent(failed.sessionId, RetryJobEvent(id(), failed.sessionVersion, RetryJobPayload(action.actionId, action.failedJobId)))
        advanceUntilIdle()
        val done = repo.getSession(failed.sessionId).data
        assertNotNull(done.candidate); assertNull(done.assessment)
        assertEquals(1, done.messages.count { it.role == "user" })
    }
    @Test fun unclearImageScenarioReturnsTypedUploadAction() = runTest {
        val repo = FakeSessionRepository(this, scenario = FakeSessionRepository.Scenario.REQUEST_CLEARER_IMAGE)
        val pending = upload(repo, create(repo)); advanceUntilIdle()
        val s = repo.getSession(pending.sessionId).data
        assertNull(s.candidate); assertNull(s.assessment)
        assertTrue(s.pendingActions.single() is UploadImageAction)
    }
    @Test fun evidenceFlowNeverProducesVerdictAndValidatesUnit() = runTest {
        val repo = FakeSessionRepository(this); val pending = upload(repo, create(repo)); advanceUntilIdle()
        var s = repo.getSession(pending.sessionId).data
        val confirm = s.pendingActions.filterIsInstance<ConfirmRevisionAction>().single()
        repo.submitEvent(s.sessionId, ConfirmCandidateEvent(id(), s.sessionVersion, s.candidate!!.revision, ConfirmPayload(confirm.actionId)))
        advanceUntilIdle(); s = repo.getSession(s.sessionId).data
        val measurement = s.pendingActions.filterIsInstance<EnterMeasurementAction>().single()
        error(SessionErrorCode.VALIDATION_ERROR) {
            repo.submitEvent(s.sessionId, SubmitMeasurementEvent(id(), s.sessionVersion, s.candidate!!.revision, MeasurementPayload(measurement.actionId, measurement.measurementId, 5.0, "A")))
        }
        assertEquals(s, repo.getSession(s.sessionId).data)
        repo.submitEvent(s.sessionId, SubmitMeasurementEvent(id(), s.sessionVersion, s.candidate!!.revision, MeasurementPayload(measurement.actionId, measurement.measurementId, 5.0, "V")))
        advanceUntilIdle(); s = repo.getSession(s.sessionId).data
        val check = s.pendingActions.single() as PerformCheckAction
        repo.submitEvent(s.sessionId, SubmitCheckResultEvent(id(), s.sessionVersion, s.candidate!!.revision, CheckPayload(check.actionId, check.checkId, "passed")))
        advanceUntilIdle(); s = repo.getSession(s.sessionId).data
        assertEquals(SessionStatus.READY, s.status); assertNull(s.assessment)
        assertTrue(s.messages.filter { it.role == "assistant" }.all { it.text.startsWith("[DEMO]") })
    }
    @Test fun invalidUploadsLeaveSessionUntouched() = runTest {
        val repo = FakeSessionRepository(this); val s = create(repo)
        error(SessionErrorCode.VALIDATION_ERROR) { repo.uploadImage(s.sessionId, s.sessionVersion, image(), " ", id()) }
        error(SessionErrorCode.UNSUPPORTED_IMAGE) { repo.uploadImage(s.sessionId, s.sessionVersion, SessionImage(byteArrayOf(1, 2), "image/png"), "Circuit", id()) }
        error(SessionErrorCode.IMAGE_TOO_LARGE) { repo.uploadImage(s.sessionId, s.sessionVersion, SessionImage(ByteArray(5 * 1024 * 1024 + 1), "image/jpeg"), "Circuit", id()) }
        assertEquals(s, repo.getSession(s.sessionId).data)
    }
    @Test fun busySessionRejectsNewOperationButAllowsClose() = runTest {
        val repo = FakeSessionRepository(this); val pending = upload(repo, create(repo))
        val e = error(SessionErrorCode.JOB_IN_PROGRESS) { repo.submitEvent(pending.sessionId, MessageEvent(id(), pending.sessionVersion, MessagePayload("Hi"))) }
        assertTrue(e.retryable); assertEquals(pending, repo.getSession(pending.sessionId).data)
    }
    @Test fun unavailableExperimentAndUnknownVersionAreRejected() = runTest {
        val repo = FakeSessionRepository(this, unavailableExperimentIds = setOf("rc-low-pass-filter"))
        error(SessionErrorCode.EXPERIMENT_UNAVAILABLE) { repo.createSession(CreateSessionRequest("rc-low-pass-filter", "1"), id()) }
        error(SessionErrorCode.EXPERIMENT_VERSION_UNAVAILABLE) { repo.createSession(CreateSessionRequest("ohms-law", "99"), id()) }
    }
    @Test fun wireJsonUsesContractNamesAndConnectionOperationDiscriminator() = runTest {
        val json = Json { encodeDefaults = true }
        val event: SessionEvent = SubmitCorrectionEvent(id(), 8, 3, CorrectionPayload(id(), listOf(RemoveConnection("wire-1"))))
        val wire = json.parseToJsonElement(json.encodeToString(event)).jsonObject
        assertEquals("submit_correction", wire.getValue("type").jsonPrimitive.content)
        assertEquals(8, wire.getValue("expected_session_version").jsonPrimitive.int)
        val change = wire.getValue("payload").jsonObject.getValue("connection_changes").jsonArray.first().jsonObject
        assertEquals("remove", change.getValue("operation").jsonPrimitive.content)
        assertFalse(change.containsKey("type"))
        assertEquals(event, json.decodeFromString<SessionEvent>(wire.toString()))
        val repo = FakeSessionRepository(this)
        val snapshot = create(repo)
        val encoded = json.encodeToString(snapshot)
        assertTrue(encoded.contains("\"mode\":\"stub\"")); assertTrue(encoded.contains("\"assessment\":null"))
        assertEquals(snapshot, json.decodeFromString<SessionSnapshot>(encoded))
        val response = repo.getSession(snapshot.sessionId)
        val envelope = json.parseToJsonElement(json.encodeToString(response)).jsonObject
        assertEquals(setOf("request_id", "data"), envelope.keys)
        val failure = error(SessionErrorCode.STALE_SESSION) {
            repo.submitEvent(snapshot.sessionId, MessageEvent(id(), 99, MessagePayload("Hi")))
        }
        val errorJson = json.parseToJsonElement(json.encodeToString(failure.toResponse())).jsonObject
        assertEquals("STALE_SESSION", errorJson.getValue("error").jsonObject.getValue("code").jsonPrimitive.content)
        assertTrue(errorJson.getValue("error").jsonObject.containsKey("current_session"))
    }
}
