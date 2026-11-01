package com.example.gitgood.data.model.wirereview

import com.example.gitgood.data.backend.BackendSession
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class WireReviewTest {
    private val identity = ReviewIdentity("student", "session", "a".repeat(64), 200, 200, "board", 3)
    private fun empty() = WireReviewState(identity, GridProposal("unavailable"))
    private fun pair(state: WireReviewState = empty()): WireReviewState {
        var s = reduceWireReview(state, WireReviewAction.AddWire)
        s = reduceWireReview(s, WireReviewAction.Tap(FramePoint(20.0, 30.0)))
        return reduceWireReview(s, WireReviewAction.Tap(FramePoint(80.0, 90.0)))
    }

    @Test fun letterboxAndOutsideTapsAreRejected() {
        val t = FrameTransform(200, 100, 300.0, 300.0)
        assertNull(t.toImage(FramePoint(150.0, 20.0)))
        assertNull(t.toImage(FramePoint(300.0, 150.0)))
        assertEquals(FramePoint(100.0, 50.0), t.toImage(FramePoint(150.0, 150.0)))
    }

    @Test fun zoomAndPanRoundTripNativeCoordinates() {
        val t = FrameTransform(200, 200, 400.0, 400.0)
            .zoomAt(FramePoint(160.0, 180.0), 2.0, 10.0, -10.0)
        val original = FramePoint(80.0, 90.0)
        val restored = t.toImage(t.toView(original))!!
        assertEquals(original.x, restored.x, .00001)
        assertEquals(original.y, restored.y, .00001)
        assertEquals(8.0, t.zoomAt(FramePoint(200.0, 200.0), 100.0).zoom, 0.0)
    }

    @Test fun tapsRequireExplicitPairingAndNeverAssignPhysicalHoles() {
        val idle = reduceWireReview(empty(), WireReviewAction.Tap(FramePoint(20.0, 30.0)))
        assertTrue(idle.wires.isEmpty())
        val first = reduceWireReview(reduceWireReview(empty(), WireReviewAction.AddWire),
            WireReviewAction.Tap(FramePoint(20.0, 30.0)))
        assertTrue(first.wires.isEmpty())
        assertTrue(first.dirty)
        val paired = pair()
        assertEquals(1, paired.wires.size)
        assertNull(paired.wires.single().a.reportedHole)
        assertFalse(paired.canSubmit)
    }

    @Test fun editDeleteUndoAndDiscardPreserveOtherEndpoint() {
        val paired = pair()
        val edit = reduceWireReview(paired, WireReviewAction.EditEnd("W1", 0))
        val changed = reduceWireReview(edit, WireReviewAction.Tap(FramePoint(40.0, 50.0)))
        assertEquals(paired.wires[0].b, changed.wires[0].b)
        val removed = reduceWireReview(changed, WireReviewAction.DeleteWire("W1"))
        assertTrue(removed.wires.isEmpty())
        assertEquals(changed.wires, reduceWireReview(removed, WireReviewAction.Undo).wires)
        assertFalse(reduceWireReview(changed, WireReviewAction.Discard).dirty)
    }

    @Test fun cancelDropsUnfinishedPair() {
        val pending = reduceWireReview(reduceWireReview(empty(), WireReviewAction.AddWire),
            WireReviewAction.Tap(FramePoint(30.0, 30.0)))
        val canceled = reduceWireReview(pending, WireReviewAction.CancelPair)
        assertFalse(canceled.dirty)
        assertTrue(canceled.wires.isEmpty())
    }

    @Test fun ambiguousSnapRetainsUnknownAndAlternatives() {
        val grid = GridProposal("needs_orientation_review", mapOf("A1" to FramePoint(10.0, 10.0), "B1" to FramePoint(20.0, 10.0)))
        val middle = provisionalEndpoint(FramePoint(15.0, 10.0), grid)
        assertNull(middle.provisionalHole)
        assertNull(middle.reportedHole)
        assertEquals(listOf("A1", "B1"), middle.alternatives)
        assertEquals("A1", provisionalEndpoint(FramePoint(10.0, 10.0), grid).provisionalHole)
    }

    @Test fun orientationSupportsReversedRowsAndSwappedStrips() {
        val reversed = previewLabelMap(10, "E10", "F1")!!
        assertEquals("E10", reversed["A1"])
        assertEquals("A1", reversed["E10"])
        assertEquals("F1", reversed["F1"])
        assertEquals("F1", previewLabelMap(10, "F1", "A10")!!["A1"])
        assertNull(previewLabelMap(10, "A1", "E10"))
        assertNull(previewLabelMap(10, "A2", "F1"))
    }

    private val board = buildJsonObject {
        put("id", "board")
        put("groups", buildJsonArray {
            for (r in 1..10) for (strip in listOf('A'..'E', 'F'..'J'))
                add(buildJsonArray { strip.forEach { add("$it$r") } })
        })
    }
    private fun snapshot(hash: String = identity.imageHash, fingerprint: String = centralBoardFingerprint(board)!!.first): BackendSession {
        val grid = buildJsonObject {
            put("schema_version", "ml1-grid-proposal-1")
            put("status", "needs_orientation_review")
            put("image_sha256", hash)
            put("image_size", buildJsonArray { add(200); add(200) })
            put("board_fingerprint", fingerprint)
            put("labels_confirmed", true)
            put("reviewed", true)
            put("holes", buildJsonObject {
                for (c in 'A'..'J') for (r in 1..10)
                    put("$c$r", buildJsonArray { add(20 + (c-'A')*10); add(20+r*10) })
            })
        }
        return BackendSession("session", 5, "awaiting_review", "experiment", "1", "",
            candidate_revision = 3, board = board,
            image = buildJsonObject { put("sha256", identity.imageHash); put("width", 200); put("height", 200) },
            ml1 = buildJsonObject { put("grid_proposal", grid) })
    }

    @Test fun gridMetadataIsBoundToFrameAndBoard() {
        val valid = parseWireReview(snapshot(), "student")!!
        assertEquals(100, valid.grid.holes.size)
        assertFalse(valid.alignmentLooksCorrect)
        assertFalse(valid.canSubmit)
        assertTrue(parseWireReview(snapshot(hash = "b".repeat(64)), "student")!!.grid.holes.isEmpty())
        assertTrue(parseWireReview(snapshot(fingerprint = "wrong"), "student")!!.grid.holes.isEmpty())
    }

    @Test fun changedRevisionAndAccountChangeDraftIdentity() {
        val session = snapshot()
        val first = parseWireReview(session, "student")!!
        assertNotEquals(first.identity, parseWireReview(session.copy(candidate_revision = 4), "student")!!.identity)
        assertNotEquals(first.identity, parseWireReview(session, "other")!!.identity)
        assertNotEquals(first.identity, parseWireReview(session.copy(image = buildJsonObject {
            put("sha256", "b".repeat(64)); put("width", 200); put("height", 200)
        }), "student")!!.identity)
    }

    @Test fun absentGridKeepsManualReviewAvailable() {
        val state = parseWireReview(snapshot().copy(ml1 = JsonObject(emptyMap())), "student")!!
        assertTrue(state.grid.holes.isEmpty())
        assertNotNull(state.grid.reason)
        assertEquals(1, pair(state).wires.size)
    }
}
