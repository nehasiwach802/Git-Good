package com.example.gitgood.ui.theme.screen.conversation

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.gitgood.data.backend.BackendSession
import kotlinx.serialization.json.*

/** Controls come from snapshot.actions, never from parsing an assistant's prose. */
@Composable
fun SessionActions(session: BackendSession, enabled: Boolean, contract: JsonObject, submit: (String, JsonObject) -> Unit) {
    var expanded by remember(session.session_id) { mutableStateOf(false) }
    TextButton(onClick = { expanded = true }, enabled = session.actions.isNotEmpty() && enabled) {
        Text("Review required actions (${session.actions.size})")
    }
    if (expanded) AlertDialog(
        onDismissRequest = { expanded = false },
        title = { Text("Circuit review") },
        text = {
            Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                session.actions.forEach { action ->
                    val type = action["type"]?.jsonPrimitive?.contentOrNull
                    when {
                        type == "retry_extraction" -> {
                            Text("Retry extraction. The previous provider request may already have run.")
                            Button(onClick = { expanded = false; submit("retry_extraction", buildJsonObject {}) }, enabled = enabled) { Text("Retry extraction") }
                        }
                        type == "review_candidate" -> CandidateReview(session, enabled, contract) { event, payload -> expanded = false; submit(event, payload) }
                        type == "upload_image" -> Text("An image upload is required. Retry the upload from the conversation.")
                        action["check_id"] != null -> {
                            Text(readable(action))
                            if (action["requires_instructor"]?.jsonPrimitive?.booleanOrNull == true) Text("Instructor supervision is required for this check.")
                            EvidenceForms(session, contract, enabled) { event, payload -> expanded = false; submit(event, payload) }
                            var observation by remember(session.session_version, action.toString()) { mutableStateOf("") }
                            OutlinedTextField(observation, { observation = it }, label = { Text("Observation / instructor feedback") })
                            Button(onClick = {
                                expanded = false
                                submit("check_result", buildJsonObject { put("check_id", action.getValue("check_id")); put("observation", observation.trim()) })
                            }, enabled = enabled && observation.isNotBlank() && observation.codePointCount(0, observation.length) <= 2000) { Text("Submit observation") }
                        }
                        else -> Text("This action needs additional support in the app:\n${readable(action)}")
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { expanded = false }) { Text("Done") } }
    )
}

@Composable
private fun CandidateReview(session: BackendSession, enabled: Boolean, contract: JsonObject, submit: (String, JsonObject) -> Unit) {
    val candidate = session.candidate
    val revision = session.candidate_revision ?: return
    var reviewed by remember(session.session_id, revision) { mutableStateOf(false) }
    Text("Candidate revision $revision. Compare every component, connection, and board layout with your photo before confirming.")
    candidate?.let { Text(readable(it)) }
    Text("Board layout")
    Text(readable(session.board))
    var target by remember(revision) { mutableStateOf("") }
    var hole by remember(revision) { mutableStateOf("") }
    var external by remember(revision) { mutableStateOf(false) }
    Text("Correct a connection using its displayed component.pin, wire.a / wire.b, or port ID.")
    OutlinedTextField(target, { target = it }, label = { Text("Connection ID") })
    OutlinedTextField(hole, { hole = it }, label = { Text(if (external) "External terminal" else "Board hole") })
    Row { Checkbox(external, { external = it }); Text("External terminal") }
    Button(onClick = {
        submit("correct_endpoint", buildJsonObject {
            put("candidate_revision", revision); put("target", target.trim())
            put(if (external) "external_terminal" else "hole", hole.trim())
        })
    }, enabled = enabled && target.isNotBlank() && hole.isNotBlank()) { Text("Save correction") }
    CandidateValues(session, enabled, submit)
    CorrespondenceAndSources(session, contract, enabled, submit)
    Row { Checkbox(reviewed, { reviewed = it }); Text("I reviewed all connections and the board.") }
    Button(onClick = {
        submit("confirm_candidate", buildJsonObject {
            put("candidate_revision", revision)
            put("acknowledgement", "reviewed_all_connections_and_board")
        })
    }, enabled = enabled && reviewed) { Text("Confirm revision $revision") }
    Text("Unresolved connections or missing values must be corrected before the server accepts confirmation. This screen does not automatically confirm a circuit.")
}

private fun readable(value: JsonElement): String = when (value) {
    is JsonObject -> value.entries.joinToString("\n") { (key, item) -> "${key.replace('_', ' ')}: ${readable(item)}" }
    is JsonArray -> value.joinToString("\n") { readable(it) }
    is JsonPrimitive -> value.content
}
