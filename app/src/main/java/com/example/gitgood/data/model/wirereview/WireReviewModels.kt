package com.example.gitgood.data.model.wirereview

import kotlin.math.*

/** Native decoded-frame pixels. No display/density coordinates are stored in a draft. */
data class FramePoint(val x: Double, val y: Double) {
    fun distance(other: FramePoint) = hypot(x - other.x, y - other.y)
}
data class ReviewIdentity(val account: String?, val sessionId: String, val imageHash: String,
    val width: Int, val height: Int, val boardIdentity: String, val candidateRevision: Int, val gridStamp: String = "")
data class GridProposal(val status: String, val holes: Map<String, FramePoint> = emptyMap(),
    val rows: Int = 0, val reason: String? = null)
data class EndpointRegion(val id: String, val left: Double, val top: Double, val right: Double, val bottom: Double)
data class WireEndpoint(val point: FramePoint? = null, val reportedHole: String? = null,
    val provisionalHole: String? = null, val alternatives: List<String> = emptyList())
data class ReviewWire(val id: String, val a: WireEndpoint, val b: WireEndpoint)
data class EndpointSelection(val wireId: String, val end: Int)

data class WireReviewState(
    val identity: ReviewIdentity,
    val grid: GridProposal,
    val regions: List<EndpointRegion> = emptyList(),
    val baseline: List<ReviewWire> = emptyList(),
    val wires: List<ReviewWire> = baseline,
    val adding: Boolean = false,
    val firstEnd: WireEndpoint? = null,
    val editing: EndpointSelection? = null,
    val history: List<List<ReviewWire>> = emptyList(),
    val alignmentLooksCorrect: Boolean = false,
    val leftTop: String = "",
    val rightTop: String = "",
    val notice: String? = null,
    val gridApproved: Boolean = false
) {
    val dirty get() = wires != baseline || firstEnd != null
    // Raw ML1 reviewed/labels_confirmed flags never grant public server approval.
    val canSubmit get() = false
}

sealed interface WireReviewAction {
    data object AddWire : WireReviewAction
    data class Tap(val point: FramePoint) : WireReviewAction
    data class EditEnd(val wireId: String, val end: Int) : WireReviewAction
    data class DeleteWire(val wireId: String) : WireReviewAction
    data object CancelPair : WireReviewAction
    data object RejectAlignment : WireReviewAction
    data object Undo : WireReviewAction
    data object Discard : WireReviewAction
    data class Alignment(val value: Boolean) : WireReviewAction
    data class LeftLabel(val value: String) : WireReviewAction
    data class RightLabel(val value: String) : WireReviewAction
}

/** Zoom is about the image origin; centroid anchoring is explicitly incorporated in zoomAt. */
data class FrameTransform(val imageWidth: Int, val imageHeight: Int, val viewWidth: Double,
    val viewHeight: Double, val zoom: Double = 1.0, val panX: Double = 0.0, val panY: Double = 0.0) {
    val fit get() = min(viewWidth / imageWidth, viewHeight / imageHeight)
    val offsetX get() = (viewWidth - fit * imageWidth) / 2
    val offsetY get() = (viewHeight - fit * imageHeight) / 2
    fun toView(point: FramePoint) = FramePoint(offsetX + panX + fit * zoom * point.x, offsetY + panY + fit * zoom * point.y)
    fun toImage(point: FramePoint): FramePoint? {
        if (fit <= 0 || !fit.isFinite() || zoom <= 0) return null
        val p = FramePoint((point.x - offsetX - panX) / (fit * zoom), (point.y - offsetY - panY) / (fit * zoom))
        return p.takeIf { it.x.isFinite() && it.y.isFinite() && it.x >= 0 && it.y >= 0 && it.x < imageWidth && it.y < imageHeight }
    }
    fun zoomAt(center: FramePoint, factor: Double, dx: Double = 0.0, dy: Double = 0.0): FrameTransform {
        val next = (zoom * factor).coerceIn(1.0, 8.0)
        val ratio = next / zoom
        return copy(zoom = next,
            panX = center.x - offsetX - (center.x - offsetX - panX) * ratio + dx,
            panY = center.y - offsetY - (center.y - offsetY - panY) * ratio + dy).constrained()
    }
    fun constrained(): FrameTransform {
        fun axis(view: Double, rendered: Double, offset: Double, pan: Double) =
            if (rendered <= view) (view - rendered) / 2 - offset else pan.coerceIn(view - rendered - offset, -offset)
        return copy(panX = axis(viewWidth, fit * zoom * imageWidth, offsetX, panX),
            panY = axis(viewHeight, fit * zoom * imageHeight, offsetY, panY))
    }
}

/** A conservative local highlight only. It never sets reportedHole or server acceptance. */
fun provisionalEndpoint(point: FramePoint, grid: GridProposal): WireEndpoint {
    val nearest = grid.holes.entries.sortedBy { it.value.distance(point) }.take(2)
    if (nearest.isEmpty()) return WireEndpoint(point = point)
    val first = nearest[0]
    val pitch = grid.holes.filterKeys { it != first.key }.values.minOfOrNull { it.distance(first.value) } ?: return WireEndpoint(point)
    val distance = first.value.distance(point)
    val secondDistance = nearest.getOrNull(1)?.value?.distance(point) ?: Double.POSITIVE_INFINITY
    if (abs(secondDistance - distance) <= pitch * .12 && distance <= pitch * .75) {
        return WireEndpoint(point = point, alternatives = nearest.map { it.key })
    }
    return WireEndpoint(point = point, provisionalHole = first.key.takeIf { distance <= pitch * .35 })
}

/** Preview labels only. The backend must independently accept the two corner choices. */
fun previewLabelMap(rows: Int, leftTop: String, rightTop: String): Map<String, String>? {
    if (rows !in 10..70) return null
    val result = mutableMapOf<String, String>()
    for ((source, input) in listOf("ABCDE" to leftTop, "FGHIJ" to rightTop)) {
        val match = Regex("([AEFJ])([1-9][0-9]*)").matchEntire(input.trim().uppercase()) ?: return null
        val column = match.groupValues[1]
        val row = match.groupValues[2].toIntOrNull() ?: return null
        if (row != 1 && row != rows) return null
        val target = when (column) { "A" -> "ABCDE"; "E" -> "EDCBA"; "F" -> "FGHIJ"; else -> "JIHGF" }
        source.zip(target).forEach { (a, b) -> for (r in 1..rows) result["$a$r"] = "$b${if (row == 1) r else rows + 1 - r}" }
    }
    return result.takeIf { it.values.toSet().size == rows * 10 }
}

fun reduceWireReview(state: WireReviewState, action: WireReviewAction): WireReviewState {
    fun changed(wires: List<ReviewWire>) = state.copy(wires = wires, history = (state.history + listOf(state.wires)).takeLast(50),
        firstEnd = null, adding = false, editing = null, notice = "Local draft only. Hole labels and server changes are not confirmed.")
    return when (action) {
        WireReviewAction.AddWire -> if (state.wires.size >= 100) state.copy(notice = "At most 100 local wires can be reviewed.")
            else state.copy(adding = true, firstEnd = null, editing = null, notice = "Tap end A, then end B of the same physical wire.")
        is WireReviewAction.Tap -> {
            val p = action.point
            if (!p.x.isFinite() || !p.y.isFinite() || p.x < 0 || p.y < 0 || p.x >= state.identity.width || p.y >= state.identity.height) state
            else if (!state.adding && state.editing == null) state.copy(notice = "Choose Add wire or an existing wire’s Edit A / Edit B first.")
            else {
                val endpoint = provisionalEndpoint(p, state.grid)
                val editing = state.editing
                if (editing != null) changed(state.wires.map { if (it.id != editing.wireId) it else if (editing.end == 0) it.copy(a = endpoint) else it.copy(b = endpoint) })
                else if (state.firstEnd == null) state.copy(firstEnd = endpoint, notice = "End A selected. Tap end B of this same wire, or cancel the pair.")
                else if (state.firstEnd.point!!.distance(p) < 1.0) state.copy(notice = "Choose a different position for end B, or cancel the pair.")
                else {
                    var number = 1
                    while (state.wires.any { it.id == "W$number" }) number++
                    changed(state.wires + ReviewWire("W$number", state.firstEnd, endpoint))
                }
            }
        }
        is WireReviewAction.EditEnd -> if (action.end !in 0..1 || state.wires.none { it.id == action.wireId }) state
            else state.copy(editing = EndpointSelection(action.wireId, action.end), adding = false, firstEnd = null, notice = "Tap the replacement position for ${action.wireId} end ${if (action.end == 0) "A" else "B"}.")
        is WireReviewAction.DeleteWire -> if (state.wires.none { it.id == action.wireId }) state else changed(state.wires.filterNot { it.id == action.wireId })
        WireReviewAction.RejectAlignment -> state.copy(alignmentLooksCorrect = false, notice = "Alignment was not approved. Use manual hole entry or return Home for a clearer video.")
        WireReviewAction.CancelPair -> state.copy(adding = false, firstEnd = null, editing = null, notice = "Unfinished selection canceled.")
        WireReviewAction.Undo -> state.history.lastOrNull()?.let { state.copy(wires = it, history = state.history.dropLast(1), adding = false, firstEnd = null, editing = null, notice = "Last local edit undone.") } ?: state
        WireReviewAction.Discard -> state.copy(wires = state.baseline, history = emptyList(), adding = false, firstEnd = null, editing = null, notice = "Local edits discarded. Server wiring is unchanged.")
        is WireReviewAction.Alignment -> state.copy(alignmentLooksCorrect = action.value)
        is WireReviewAction.LeftLabel -> state.copy(leftTop = action.value.take(8).uppercase())
        is WireReviewAction.RightLabel -> state.copy(rightTop = action.value.take(8).uppercase())
    }
}
