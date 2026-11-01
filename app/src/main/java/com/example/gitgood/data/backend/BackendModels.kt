package com.example.gitgood.data.backend

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class Catalog(val experiments: List<BackendExperiment>)

@Serializable
data class BackendExperiment(
    val experiment_id: String,
    val version: String,
    val name: String,
    val workflow_approved: Boolean = false,
    val simulated: Boolean = false,
    val review_contract: JsonObject = JsonObject(emptyMap())
) {
    val key get() = "$experiment_id@$version"
}

@Serializable
data class CreateSession(val experiment_id: String, val experiment_version: String, val description: String)

@Serializable
data class BackendMessage(val id: String, val role: String, val text: String)

/** The deployed v1.1 response is a bare snapshot, not a data envelope. */
@Serializable
data class BackendSession(
    val session_id: String,
    val session_version: Int,
    val state: String,
    val experiment_id: String,
    val experiment_version: String,
    val description: String,
    val candidate_revision: Int? = null,
    val candidate: JsonObject? = null,
    val board: JsonObject = JsonObject(emptyMap()),
    val messages: List<BackendMessage> = emptyList(),
    val actions: List<JsonObject> = emptyList(),
    val simulated: Boolean = false,
    val job_id: String? = null,
    val error: JsonObject? = null
) {
    val busy get() = state in setOf("extracting", "diagnosing", "completing")
    val closed get() = state in setOf("closed", "completed")
}

@Serializable
data class BackendEvent(
    val event_id: String,
    val expected_session_version: Int,
    val type: String,
    val payload: JsonObject
)

class BackendException(val status: Int, message: String) : Exception(message)
