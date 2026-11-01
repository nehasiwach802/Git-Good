package com.example.gitgood.ui.theme.screen.conversation

import kotlinx.serialization.json.*
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.gitgood.data.model.wirereview.*
import com.example.gitgood.ui.theme.*
import kotlin.math.roundToInt

@Composable
internal fun WireReviewPanel(
    frame: Uri?, state: WireReviewState, enabled: Boolean,
    frameId: String?, submit: (String, JsonObject) -> Unit,
    onAction: (WireReviewAction) -> Unit,
    onRefresh: () -> Unit,
    onNewVideo: () -> Unit
) {
    val identity = state.identity
    val fingerprint = identity.boardIdentity.substringBefore(':')
    val frameReady = frame != null && frameId?.matches(Regex("F[1-6]")) == true &&
        fingerprint.matches(Regex("[0-9a-f]{64}"))
    fun sendBoundEvent(type: String, fields: JsonObjectBuilder.() -> Unit) {
        if (!frameReady || !enabled) return
        submit(type, buildJsonObject {
            put("candidate_revision", identity.candidateRevision)
            put("frame_id", frameId)
            put("image_sha256", identity.imageHash)
            put("board_fingerprint", fingerprint)
            fields()
        })
    }
    val drafts = state.wires.filter { wire -> state.baseline.none { it.id == wire.id } }
    var showRegions by remember(state.identity) { mutableStateOf(false) }
    val labels = if (state.alignmentLooksCorrect) previewLabelMap(state.grid.rows, state.leftTop, state.rightTop) else null
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Touch-based wire review", style = MaterialTheme.typography.titleMedium)
        Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {
            Text(when {
                state.gridApproved -> "Grid approved. Mark both ends of each wire, then save the pairs together."
                state.grid.holes.isNotEmpty() -> "Grid approval is below the frame. Check the dots, enter both printed corner labels, then tap Approve grid."
                else -> "Grid approval is unavailable for this video. See the reason below the frame."
            },
                Modifier.padding(12.dp), color = PrimaryTextColor, style = MaterialTheme.typography.bodySmall)
        }
        if (frame != null) {
            WireReviewCanvas(frame, state, enabled, showRegions) { onAction(WireReviewAction.Tap(it)) }
        } else Text("Waiting for the selected frame. Use Refresh review if it does not load.", color = SecondaryTextColor)
        Text("Dots: provisional grid · Amber boxes: unreviewed suggestions · Hollow circles/squares: unresolved ends A/B · White ring: selection",
            color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall)
        if (state.regions.isNotEmpty()) {
            Row {
                Checkbox(showRegions, { showRegions = it })
                Text("Show ${state.regions.size} endpoint-region suggestions. Boxes do not identify holes or wire pairs.", Modifier.weight(1f))
            }
        } else Text("No detector suggestions are available.", color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall)
        if (state.gridApproved) {
            Text("Grid approved. You can add and save wire pairs.", color = PrimaryGreen)
        } else if (state.grid.holes.isNotEmpty()) {
            Text("Step 1 · Approve grid", style = MaterialTheme.typography.titleMedium)
            Text("Do the dots line up with the holes?", fontWeight = FontWeight.Medium)
            Row {
                Checkbox(state.alignmentLooksCorrect, { onAction(WireReviewAction.Alignment(it)) }, enabled = enabled)
                Text("The dots look aligned (local check only)", Modifier.weight(1f))
            }
            TextButton(onClick = { onAction(WireReviewAction.RejectAlignment) }, enabled = enabled) { Text("The dots do not line up") }
            Text("The two large amber rings mark the provisional top-left holes of the left and right five-column strips. Enter their printed labels; numbering may run in opposite directions.",
                color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(state.leftTop, { onAction(WireReviewAction.LeftLabel(it)) }, enabled = enabled,
                modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("Printed label at left strip’s top-left hole") })
            OutlinedTextField(state.rightTop, { onAction(WireReviewAction.RightLabel(it)) }, enabled = enabled,
                modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("Printed label at right strip’s top-left hole") })
            if (state.leftTop.isNotBlank() || state.rightTop.isNotBlank()) {
                Text(if (previewLabelMap(state.grid.rows, state.leftTop, state.rightTop) == null)
                    "Choose corner labels A/E and F/J at row 1 or ${state.grid.rows}; the two labels must describe different strips."
                else "Label preview is valid, but physical-hole assignments still need server approval.", color = SecondaryTextColor,
                    style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = {
                sendBoundEvent("accept_grid") {
                    put("left_top", state.leftTop.trim())
                    put("right_top", state.rightTop.trim())
                    put("acknowledgement", "reviewed_grid_alignment_and_printed_labels")
                }
            }, enabled = enabled && frameReady && labels != null && !state.dirty, modifier = Modifier.fillMaxWidth()) { Text("Approve grid") }
            if (!state.alignmentLooksCorrect) Text("Tick The dots look aligned after checking the frame.", color = SecondaryTextColor)
            else if (labels == null) Text("Enter valid printed labels in both fields to enable approval.", color = SecondaryTextColor)
            else if (state.dirty) Text("Discard unsaved wire edits below, then approve the grid.", color = SecondaryTextColor)
        } else {
            Text("Grid required before adding wires", style = MaterialTheme.typography.titleMedium)
            Button(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) { Text("Approve grid · grid unavailable") }
            Text(state.grid.reason ?: "Automatic alignment is not available for this capture. Use manual hole entry below.", color = SecondaryTextColor)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onRefresh, enabled = enabled) { Text("Refresh review") }
            TextButton(onClick = onNewVideo, enabled = enabled) { Text("Use a clearer video") }
        }
        Text("Wire pairs", fontWeight = FontWeight.Medium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onAction(WireReviewAction.AddWire) }, enabled = enabled && frame != null && state.wires.size < 100 && !state.adding && state.editing == null && frameReady && state.gridApproved) { Text("Add wire") }
            TextButton(onClick = { onAction(WireReviewAction.Undo) }, enabled = enabled && state.history.isNotEmpty()) { Text("Undo") }
        }
        if (state.adding || state.editing != null) {
            Text(state.notice ?: "Tap the selected wire end.", color = PrimaryGreen)
            TextButton(onClick = { onAction(WireReviewAction.CancelPair) }, enabled = enabled) { Text("Cancel selection") }
        } else state.notice?.let { Text(it, color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall) }
        fun endpointLabel(endpoint: WireEndpoint): String {
            endpoint.reportedHole?.let { return "$it (server-reported, unreviewed)" }
            val p = endpoint.point
            val coordinates = p?.let { " at (${it.x.roundToInt()}, ${it.y.roundToInt()}) px" }.orEmpty()
            if (endpoint.alternatives.isNotEmpty()) return "Unknown$coordinates · ambiguous: ${endpoint.alternatives.joinToString()}"
            val hint = endpoint.provisionalHole
            val preview = labels?.get(hint)
            return "Unknown$coordinates" + if (hint != null) " · ${preview ?: hint} (${if (preview != null) "label preview" else "provisional grid"})" else " · zoom in or use manual entry"
        }
        if (state.wires.isEmpty()) Text("No wires listed. Add wire, then tap its two visible insertion ends. Hidden ends must stay unknown.", color = SecondaryTextColor)
        state.wires.forEach { wire ->
            Surface(shape = RoundedCornerShape(10.dp), border = BorderStroke(1.dp, BorderColor), color = MaterialTheme.colorScheme.surfaceContainerLow) {
                Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(wire.id, fontWeight = FontWeight.Medium)
                    Text("A: ${endpointLabel(wire.a)}", style = MaterialTheme.typography.bodySmall)
                    Text("B: ${endpointLabel(wire.b)}", style = MaterialTheme.typography.bodySmall)
                    if (wire in drafts) Row {
                        TextButton(onClick = { onAction(WireReviewAction.EditEnd(wire.id, 0)) }, enabled = enabled && frame != null) { Text("Edit A") }
                        TextButton(onClick = { onAction(WireReviewAction.EditEnd(wire.id, 1)) }, enabled = enabled && frame != null) { Text("Edit B") }
                        TextButton(onClick = { onAction(WireReviewAction.DeleteWire(wire.id)) }, enabled = enabled) { Text("Delete") }
                    }
                }
            }
        }
        if (state.dirty) {
            Text("Finish and save this wire before confirming the circuit.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { onAction(WireReviewAction.Discard) }, enabled = enabled) { Text("Discard local edits") }
        }
        if (!frameReady) Text("Wire saving requires the selected frame and a matching breadboard profile.")
        val newWire = drafts.firstOrNull()
        val a = newWire?.a?.point
        val b = newWire?.b?.point
        if (newWire != null && a != null && b != null) {
            Button(onClick = {
                sendBoundEvent("add_wire") {
                    put("wire_id", newWire.id)
                    put("a_xy", buildJsonArray { add(a.x); add(a.y) })
                    put("b_xy", buildJsonArray { add(b.x); add(b.y) })
                    put("acknowledgement", "reviewed_same_physical_wire")
                }
            }, enabled = enabled && frameReady && state.gridApproved && !state.adding && state.editing == null) {
                Text("Confirm pairs and save all (${drafts.size})")
            }
        }
    }
}
