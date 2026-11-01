package com.example.gitgood.ui.theme.screen.conversation

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
    onAction: (WireReviewAction) -> Unit,
    onRefresh: () -> Unit,
    onNewVideo: () -> Unit
) {
    var showRegions by remember(state.identity) { mutableStateOf(false) }
    val labels = if (state.alignmentLooksCorrect) previewLabelMap(state.grid.rows, state.leftTop, state.rightTop) else null
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Touch-based wire review", style = MaterialTheme.typography.titleMedium)
        Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {
            Text("Local preview · Grid approval and saving new wire pairs are not supported by the server yet. Taps stay unverified; manual hole corrections below remain available.",
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
        } else Text("No detector suggestions are available. You can still mark every wire manually.", color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall)
        if (state.grid.holes.isNotEmpty()) {
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
            Button(onClick = {}, enabled = false) { Text("Approve grid · awaiting server support") }
        } else {
            Text(state.grid.reason ?: "Automatic alignment is not available for this capture. Use manual hole entry below.", color = SecondaryTextColor)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onRefresh, enabled = enabled) { Text("Refresh review") }
            TextButton(onClick = onNewVideo, enabled = enabled) { Text("Use a clearer video") }
        }
        Text("Wire pairs", fontWeight = FontWeight.Medium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onAction(WireReviewAction.AddWire) }, enabled = enabled && frame != null && state.wires.size < 100) { Text("Add wire") }
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
                    Row {
                        TextButton(onClick = { onAction(WireReviewAction.EditEnd(wire.id, 0)) }, enabled = enabled && frame != null) { Text("Edit A") }
                        TextButton(onClick = { onAction(WireReviewAction.EditEnd(wire.id, 1)) }, enabled = enabled && frame != null) { Text("Edit B") }
                        TextButton(onClick = { onAction(WireReviewAction.DeleteWire(wire.id)) }, enabled = enabled) { Text("Delete") }
                    }
                }
            }
        }
        if (state.dirty) {
            Text("Unsent local wire edits: these are not part of the server candidate. Discard them to use the existing candidate confirmation, or wait for server wire-save support.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { onAction(WireReviewAction.Discard) }, enabled = enabled) { Text("Discard local edits") }
        }
        Button(onClick = {}, enabled = false) { Text("Save wire pairs · awaiting server support") }
    }
}
