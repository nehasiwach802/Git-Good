package com.example.gitgood.data.backend

import org.junit.Assert.*
import org.junit.Test

class VideoUploadLimitsTest {
    @Test fun acceptsSixtySecond1080pVideoMetadata() {
        VideoUploadLimits.validateMetadata(60_000, 1920, 1080)
    }
    @Test fun rejectsLongClipBeforeCreatingServerSession() {
        try { VideoUploadLimits.validateMetadata(60_001, 1920, 1080); fail("Expected duration limit") }
        catch (error: IllegalArgumentException) { assertTrue(error.message!!.contains("60 seconds")) }
    }
    @Test fun rejectsUnboundedFrameDimensions() {
        try { VideoUploadLimits.validateMetadata(20_000, 7680, 4320); fail("Expected pixel limit") }
        catch (_: IllegalArgumentException) {}
    }
    @Test fun rejectsAudioOnlyOrUnreadableVideoMetadata() {
        try { VideoUploadLimits.validateMetadata(20_000, 0, 0); fail("Expected video dimensions") }
        catch (_: IllegalArgumentException) {}
    }
}
