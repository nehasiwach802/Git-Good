package com.example.gitgood.data.backend

import android.content.Context
import android.media.MediaMetadataRetriever
import android.graphics.BitmapFactory
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import javax.inject.Inject

object VideoUploadLimits {
    const val MAX_BYTES = 50L * 1024 * 1024
    const val MAX_DURATION_MS = 60_000L
    const val MAX_PIXELS = 8_500_000L
    fun validateFile(file: File) {
        require(file.isFile && file.length() in 16..MAX_BYTES) { "Choose an MP4 video up to 50 MiB." }
        val header = ByteArray(8)
        file.inputStream().use { require(it.read(header) == 8) { "Could not read the video." } }
        require(header.copyOfRange(4, 8).contentEquals("ftyp".toByteArray())) { "Choose an MP4 video. Other formats are not supported." }
    }
    fun validateMetadata(durationMs: Long, width: Long, height: Long) {
        require(durationMs in 1..MAX_DURATION_MS) { "Choose a video no longer than 60 seconds." }
        require(width > 0 && height > 0 && width <= MAX_PIXELS && height <= MAX_PIXELS && width * height <= MAX_PIXELS) {
            "Choose a video with at most 8.5 megapixels per frame (1080p recommended)."
        }
    }
}

data class PreparedSessionVideo(val path: String)

interface SessionVideoStore {
    suspend fun prepare(uri: Uri, fileName: String): PreparedSessionVideo
    suspend fun file(path: String): File
    suspend fun saveFrame(name: String, bytes: ByteArray): String
    fun preview(path: String): Uri?
    fun remove(path: String)
}

class AndroidSessionVideoStore @Inject constructor(@param:ApplicationContext private val context: Context) : SessionVideoStore {
    private fun directory() = File(context.noBackupFilesDir, "session-videos").apply {
        check(isDirectory || mkdirs()) { "Could not prepare video storage." }
    }
    override suspend fun prepare(uri: Uri, fileName: String): PreparedSessionVideo = withContext(Dispatchers.IO) {
        val file = File(directory(), fileName)
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                file.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var size = 0L
                    while (true) {
                        ensureActive()
                        val count = input.read(buffer)
                        if (count < 0) break
                        size += count
                        require(size <= VideoUploadLimits.MAX_BYTES) { "Choose an MP4 video up to 50 MiB." }
                        output.write(buffer, 0, count)
                    }
                }
            } ?: error("Could not read the selected video. Please select it again.")
            VideoUploadLimits.validateFile(file)
            val metadata = MediaMetadataRetriever()
            try {
                metadata.setDataSource(file.absolutePath)
                fun number(key: Int) = metadata.extractMetadata(key)?.toLongOrNull() ?: 0L
                VideoUploadLimits.validateMetadata(number(MediaMetadataRetriever.METADATA_KEY_DURATION),
                    number(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH), number(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT))
            } finally { metadata.release() }
            PreparedSessionVideo(file.absolutePath)
        } catch (error: Throwable) { file.delete(); throw error }
    }
    override suspend fun file(path: String): File = withContext(Dispatchers.IO) {
        File(path).also(VideoUploadLimits::validateFile)
    }
    override suspend fun saveFrame(name: String, bytes: ByteArray): String = withContext(Dispatchers.IO) {
        require(name.matches(Regex("[0-9a-f-]+"))) { "Invalid frame identity." }
        require(bytes.size in 1..5 * 1024 * 1024) { "Invalid review frame size." }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        require(bounds.outMimeType in setOf("image/jpeg", "image/png") && bounds.outWidth > 0 && bounds.outHeight > 0 &&
            bounds.outWidth <= 2000 && bounds.outHeight <= 2000) { "Invalid review frame." }
        val file = File(directory(), "$name.jpg")
        file.writeBytes(bytes)
        file.absolutePath
    }
    override fun preview(path: String): Uri = Uri.fromFile(File(path))
    override fun remove(path: String) { File(path).delete() }
}
