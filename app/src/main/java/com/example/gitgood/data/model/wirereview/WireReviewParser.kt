package com.example.gitgood.data.model.wirereview

import com.example.gitgood.data.backend.BackendSession
import kotlinx.serialization.json.*
import java.security.MessageDigest

private fun JsonObject.text(key: String) = (get(key) as? JsonPrimitive)?.contentOrNull
private fun JsonObject.int(key: String) = (get(key) as? JsonPrimitive)?.intOrNull
private fun JsonObject.objects(key: String) = (get(key) as? JsonArray)?.mapNotNull { it as? JsonObject }.orEmpty()
private fun JsonElement.pair(): FramePoint? {
    val row = this as? JsonArray ?: return null
    if (row.size != 2) return null
    val x = (row[0] as? JsonPrimitive)?.doubleOrNull ?: return null
    val y = (row[1] as? JsonPrimitive)?.doubleOrNull ?: return null
    return FramePoint(x, y).takeIf { x.isFinite() && y.isFinite() }
}
private fun digest(text: String) = MessageDigest.getInstance("SHA-256").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }
private fun canonical(value: JsonElement): String = when (value) {
    is JsonObject -> value.entries.sortedBy { it.key }.joinToString(", ", "{", "}") { "${canonical(JsonPrimitive(it.key))}: ${canonical(it.value)}" }
    is JsonArray -> value.joinToString(", ", "[", "]") { canonical(it) }
    is JsonPrimitive -> value.toString().map { if (it.code > 127) "\\u%04x".format(it.code) else it.toString() }.joinToString("")
}

/** Mirrors the ML1 central-board fingerprint only for its declared standard geometry. */
fun centralBoardFingerprint(board: JsonObject): Pair<String, Int>? {
    val groups = board["groups"] as? JsonArray ?: return null
    val holes = groups.flatMap { (it as? JsonArray)?.mapNotNull { item -> (item as? JsonPrimitive)?.contentOrNull } ?: return null }
    if (holes.isEmpty() || holes.toSet().size != holes.size) return null
    val rows = holes.map { Regex("[A-J]([1-9][0-9]*)").matchEntire(it)?.groupValues?.get(1)?.toIntOrNull() ?: return null }.maxOrNull() ?: return null
    if (rows !in 10..70) return null
    val expected = ('A'..'J').flatMap { c -> (1..rows).map { "$c$it" } }.toSet()
    if (holes.toSet() != expected) return null
    val positions = buildJsonObject {
        expected.sorted().forEach { hole ->
            val column = hole[0] - 'A'
            val p = FramePoint((column + if (column >= 5) 2 else 0).toDouble(), (hole.drop(1).toInt() - 1).toDouble())
            (board["hole_positions"] as? JsonObject)?.let { explicit -> if (explicit[hole]?.pair() != p) return null }
            put(hole, buildJsonArray { add(p.x); add(p.y) })
        }
    }
    val id = board["id"] ?: return null
    return digest(canonical(buildJsonObject { put("id", id); put("groups", groups); put("xy", positions) })) to rows
}

fun parseWireReview(session: BackendSession, account: String?): WireReviewState? {
    val image = session.image ?: return null
    val hash = image.text("sha256")?.takeIf { it.matches(Regex("[0-9a-f]{64}")) } ?: return null
    val width = image.int("width")?.takeIf { it in 1..2000 } ?: return null
    val height = image.int("height")?.takeIf { it in 1..2000 } ?: return null
    val revision = session.candidate_revision ?: return null
    val boardStamp = digest(canonical(session.board))
    val boardGeometry = centralBoardFingerprint(session.board)
    val media = session.ml1["media"] as? JsonObject
    val selected = media?.text("selected_frame_id")
    val frame = media?.objects("frames")?.firstOrNull { it.text("id") == selected }
    val rawGrid = (session.ml1["grid_proposal"] as? JsonObject)
        ?: (media?.get("grid_proposal") as? JsonObject)
        ?: (frame?.get("grid_proposal") as? JsonObject)
    fun grid(): GridProposal {
        if (rawGrid == null) return GridProposal("unavailable", reason = "No automatic grid was returned. Manual hole entry remains available below.")
        if (rawGrid.text("schema_version") != "ml1-grid-proposal-1")
            return GridProposal("unavailable", reason = "This grid format is not supported. Manual hole entry remains available.")
        val status = rawGrid.text("status") ?: "unavailable"
        val rawSize = (rawGrid["image_size"] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.intOrNull }
        if (rawGrid.text("image_sha256") != hash || rawSize != listOf(width, height))
            return GridProposal("unavailable", reason = "Grid metadata belongs to a different frame. Stale overlays are hidden.")
        if (boardGeometry == null || rawGrid.text("board_fingerprint") != boardGeometry.first)
            return GridProposal("unavailable", reason = "The grid does not match this board profile. Manual hole entry remains available.")
        if (status != "needs_orientation_review") {
            val reason = rawGrid.text("reason")
            val message = if (reason == "complete_grid_not_found") {
                "The video processor could not detect the complete ${boardGeometry.second}-row board required by this experiment. Record the whole board from above, with both five-column strips and the first and last rows visible. Keep it still and sharply focused. If your board has a different row count, the experiment’s backend board profile must be updated."
            } else reason?.take(240) ?: "Automatic alignment is unavailable; use a clearer video or manual entry."
            return GridProposal(status, reason = message)
        }
        val rawHoles = rawGrid["holes"] as? JsonObject ?: return GridProposal("unavailable", reason = "Grid coordinates are missing.")
        val points = mutableMapOf<String, FramePoint>()
        rawHoles.forEach { (id, item) ->
            val p = item.pair() ?: return GridProposal("unavailable", reason = "Grid coordinates are invalid.")
            if (p.x < 0 || p.y < 0 || p.x >= width || p.y >= height) return GridProposal("unavailable", reason = "Grid coordinates fall outside this frame.")
            points[id] = p
        }
        val expected = ('A'..'J').flatMap { c -> (1..boardGeometry.second).map { "$c$it" } }.toSet()
        if (points.keys != expected || points.values.toSet().size != points.size)
            return GridProposal("unavailable", reason = "Only a complete central A–J grid is supported. Outer rails require manual review.")
        return GridProposal(status, points, boardGeometry.second)
    }
    val regions = mutableListOf<EndpointRegion>()
    fun addRegions(data: JsonObject?) {
        data?.objects("proposals")?.take(100)?.forEachIndexed { index, proposal ->
            val box = proposal["box"] as? JsonArray ?: return@forEachIndexed
            val values = box.mapNotNull { (it as? JsonPrimitive)?.doubleOrNull?.takeIf { n -> n.isFinite() } }
            val score = (proposal["score"] as? JsonPrimitive)?.doubleOrNull ?: return@forEachIndexed
            if (values.size != 4 || !score.isFinite() || score !in 0.0..1.0) return@forEachIndexed
            val (x1, y1, x2, y2) = values
            if (x1 < 0 || y1 < 0 || x1 >= x2 || y1 >= y2 || x2 > width || y2 > height) return@forEachIndexed
            regions.add(EndpointRegion(proposal.text("id")?.take(80) ?: "P${index+1}", x1, y1, x2, y2))
        }
    }
    val detection = session.ml1["endpoint_detection"] as? JsonObject
    if (detection?.text("status") == "unreviewed_region_proposals" && detection.text("target") == "wire_end_region") {
        detection.objects("videos").flatMap { it.objects("frames") }.firstOrNull {
            it.text("sha256") == hash && (it["image_size"] as? JsonArray)?.mapNotNull { v -> (v as? JsonPrimitive)?.intOrNull } == listOf(width, height)
        }?.let(::addRegions)
    }
    val frameImage = frame?.get("image") as? JsonObject
    val normalized = frame?.get("endpoint_detection") as? JsonObject
    if (regions.isEmpty() && frameImage?.text("sha256") == hash && frameImage.int("width") == width && frameImage.int("height") == height &&
        normalized?.text("status") == "unreviewed_region_proposals") addRegions(normalized)
    fun endpoint(value: JsonElement?): WireEndpoint {
        val object_ = value as? JsonObject
        return WireEndpoint(reportedHole = object_?.text("hole")?.takeIf { it != "null" })
    }
    val wires = session.candidate?.objects("wires")?.take(100)?.mapIndexed { index, item ->
        ReviewWire(item.text("id")?.take(80) ?: "W${index+1}", endpoint(item["a"]), endpoint(item["b"]))
    }.orEmpty().distinctBy { it.id }
    return WireReviewState(ReviewIdentity(account, session.session_id, hash, width, height,
        (boardGeometry?.first ?: "unsupported") + ":" + boardStamp, revision, digest(rawGrid?.let(::canonical) ?: "none")), grid(), regions, wires,
        gridApproved = session.actions.any { action ->
            action.text("type") == "review_candidate" &&
                (action["event_types"] as? JsonArray)?.any {
                    (it as? JsonPrimitive)?.contentOrNull == "add_wire"
                } == true
        } && media?.get("grid_review") is JsonObject)
}
