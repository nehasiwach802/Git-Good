package com.example.gitgood.data.backend

/** Session operations shared by the live transport and workflow regression tests. */
interface SessionApi {
    suspend fun experiments(): List<BackendExperiment>
    suspend fun create(request: CreateSession, key: String): BackendSession
    suspend fun get(id: String): BackendSession
    suspend fun event(id: String, event: BackendEvent): BackendSession
    suspend fun upload(id: String, version: Int, bytes: ByteArray, mime: String, key: String): BackendSession
}
