package com.example.gitgood.ui.theme.screen.conversation

import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import com.example.gitgood.data.backend.BackendSession
import com.example.gitgood.data.model.wirereview.*
import com.example.gitgood.ui.theme.*
import kotlinx.serialization.json.*

/** Inline assistant form: controls come from snapshot.actions, never chat-text parsing. */
@Composable
fun SessionActions(
    session: BackendSession,
    enabled: Boolean,
    contract: JsonObject,
    submit: (String, JsonObject) -> Unit,
    reviewFrame: Uri? = null,
    frameCaption: String? = null,
    wireReview: WireReviewState? = null,
    onWireAction: (ReviewIdentity, WireReviewAction) -> Unit = { _, _ -> },
    onRefreshReview: () -> Unit = {},
    onNewVideo: () -> Unit = {}
) {
    if (session.actions.isEmpty()) return
    Surface(
        modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp),
        color = SurfaceColor, border = BorderStroke(1.dp, BorderColor)
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Circuitly", color = PrimaryGreen, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Text("Continue here", color = PrimaryTextColor, fontSize = 18.sp, fontWeight = FontWeight.Medium)
            if (wireReview == null) reviewFrame?.let {
                AsyncImage(model = it, contentDescription = "Selected video frame for circuit review",
                    modifier = Modifier.fillMaxWidth().height(200.dp), contentScale = ContentScale.Fit)
                frameCaption?.let { caption -> Text(caption, color = SecondaryTextColor, fontSize = 12.sp) }
            }
            session.actions.forEach { action ->
                val type = (action["type"] as? JsonPrimitive)?.contentOrNull
                // Message-only session updates must not discard a partially entered form.
                key(session.session_id, session.candidate_revision, session.image, session.board, type, action["check_id"]) {
                    when {
                        type == "retry_extraction" -> {
                            Text("Extraction needs another attempt. The previous provider request may already have run.")
                            Button(onClick = { submit("retry_extraction", buildJsonObject {}) }, enabled = enabled) { Text("Retry extraction") }
                        }
                        type == "review_candidate" -> {
                            listOf("pending", "reasoning_pending").forEach { field ->
                                (action[field] as? JsonArray)?.takeIf { it.isNotEmpty() }?.let { Text("Needs review: ${readable(it)}", color = SecondaryTextColor) }
                            }
                            wireReview?.let { draft ->
                                WireReviewPanel(reviewFrame, draft, enabled,
                                    ((session.ml1["media"] as? JsonObject)?.get("selected_frame_id") as? JsonPrimitive)?.contentOrNull, submit,
                                    { onWireAction(draft.identity, it) }, onRefreshReview, onNewVideo)
                            }
                            CandidateReview(session, enabled, contract, session.image == null || reviewFrame != null,
                                wireReview?.dirty != true, submit)
                        }
                        type == "upload_image" -> Text("A video upload is required. Use Retry below to resume the upload.")
                        action["check_id"] != null -> {
                            Text(readable(action))
                            if ((action["requires_instructor"] as? JsonPrimitive)?.booleanOrNull == true) Text("Instructor supervision is required for this check.")
                            EvidenceForms(session, contract, enabled, submit)
                            var observation by remember { mutableStateOf("") }
                            OutlinedTextField(observation, { observation = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled,
                                label = { Text("Observation / instructor feedback") }, maxLines = 5)
                            Button(onClick = {
                                submit("check_result", buildJsonObject { put("check_id", action.getValue("check_id")); put("observation", observation.trim()) })
                            }, enabled = enabled && observation.isNotBlank() && observation.codePointCount(0, observation.length) <= 2000) { Text("Submit observation") }
                        }
                        else -> Text("This action needs additional support in the app:\n${readable(action)}")
                    }
                }
            }
        }
    }
}

@Composable
private fun CandidateReview(session: BackendSession, enabled: Boolean, contract: JsonObject, frameAvailable: Boolean, wireEditsResolved: Boolean, submit: (String, JsonObject) -> Unit) {
    val candidate = session.candidate
    val revision = session.candidate_revision ?: return
    var reviewed by remember(session.session_id, revision) { mutableStateOf(false) }
    var showDetails by remember(session.session_id, revision) { mutableStateOf(false) }
    Text("Review revision $revision. Compare the components, connections and board layout with the frame above. Enter corrections here before confirming.")
    TextButton(onClick = { showDetails = !showDetails }) { Text(if (showDetails) "Hide circuit details" else "Show circuit details") }
    if (showDetails) {
        candidate?.let { Text(readable(it), color = SecondaryTextColor, fontSize = 13.sp) }
        Text("Board layout", fontWeight = FontWeight.Medium)
        Text(readable(session.board), color = SecondaryTextColor, fontSize = 13.sp)
    }
    var target by remember(revision) { mutableStateOf("") }
    var hole by remember(revision) { mutableStateOf("") }
    var external by remember(revision) { mutableStateOf(false) }
    Text("Correct a connection using its component.pin, wire.a / wire.b, or port ID from the circuit details.")
    OutlinedTextField(target, { target = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("Connection ID") })
    OutlinedTextField(hole, { hole = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text(if (external) "External terminal" else "Board hole") })
    Row { Checkbox(external, { external = it }, enabled = enabled); Text("External terminal", Modifier.weight(1f)) }
    Button(onClick = {
        submit("correct_endpoint", buildJsonObject {
            put("candidate_revision", revision); put("target", target.trim())
            put(if (external) "external_terminal" else "hole", hole.trim())
        })
    }, enabled = enabled && target.isNotBlank() && hole.isNotBlank()) { Text("Save correction") }
    CandidateValues(session, enabled, submit)
    CorrespondenceAndSources(session, contract, enabled, submit)
    if (!frameAvailable) Text("Wait for the selected frame to load before confirming. Use Retry below if it failed.", color = SecondaryTextColor)
    Row {
        Checkbox(reviewed, { reviewed = it }, enabled = enabled && frameAvailable && wireEditsResolved)
        Text("I reviewed all connections and the board.", Modifier.weight(1f))
    }
    Button(onClick = {
        submit("confirm_candidate", buildJsonObject {
            put("candidate_revision", revision)
            put("acknowledgement", "reviewed_all_connections_and_board")
        })
    }, enabled = enabled && frameAvailable && wireEditsResolved && reviewed) { Text("Confirm revision $revision") }
    Text("Resolve missing connections and values before confirming. You can also type a question in the message box.", color = SecondaryTextColor, fontSize = 13.sp)
}

private fun readable(value: JsonElement): String = when (value) {
    is JsonObject -> value.entries.joinToString("\n") { (key, item) -> "${key.replace('_', ' ')}: ${readable(item)}" }
    is JsonArray -> value.joinToString("\n") { readable(it) }
    is JsonPrimitive -> value.content
}
