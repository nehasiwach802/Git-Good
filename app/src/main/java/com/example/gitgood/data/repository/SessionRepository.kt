package com.example.gitgood.data.repository

import com.example.gitgood.data.model.session.*

/** Contract boundary. The current binding is offline/demo; no server integration is installed. */
interface SessionRepository {
    val demoNotice: String?
    suspend fun getHealth(): SessionHealth
    suspend fun getExperiments(): RepositoryResponse<ExperimentList>
    suspend fun createSession(request: CreateSessionRequest, idempotencyKey: String): RepositoryResponse<SessionSnapshot>
    suspend fun uploadImage(
        sessionId: String, expectedSessionVersion: Long, image: SessionImage,
        description: String, idempotencyKey: String
    ): RepositoryResponse<SessionSnapshot>
    suspend fun getSession(sessionId: String): RepositoryResponse<SessionSnapshot>
    suspend fun submitEvent(sessionId: String, event: SessionEvent): RepositoryResponse<SessionSnapshot>
}
