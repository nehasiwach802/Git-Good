package com.example.gitgood.data.backend

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import javax.inject.Inject

interface SessionImageStore {
    suspend fun prepare(uri: Uri, fileName: String): PreparedSessionImage
    suspend fun read(path: String): ByteArray
    fun preview(path: String): Uri?
    fun remove(path: String)
}

data class PreparedSessionImage(val path: String, val mime: String)

class AndroidSessionImageStore @Inject constructor(@param:ApplicationContext private val context: Context) : SessionImageStore {
    override suspend fun prepare(uri: Uri, fileName: String): PreparedSessionImage = withContext(Dispatchers.IO) {
        val bytes = context.contentResolver.openInputStream(uri)?.use { input ->
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                require(output.size() + count <= 5 * 1024 * 1024) { "Choose an image smaller than 5 MiB." }
                output.write(buffer, 0, count)
            }
            output.toByteArray()
        } ?: error("Could not read the selected image. Please select it again.")
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        require(bounds.outWidth > 0 && bounds.outHeight > 0 && bounds.outWidth.toLong() * bounds.outHeight <= 20_000_000) { "Choose an image with at most 20 megapixels." }
        require(bounds.outMimeType in setOf("image/jpeg", "image/png")) { "Choose a JPEG or PNG image." }
        val directory = File(context.noBackupFilesDir, "session-images")
        check(directory.isDirectory || directory.mkdirs()) { "Could not prepare image storage." }
        val file = File(directory, fileName)
        file.writeBytes(bytes)
        PreparedSessionImage(file.absolutePath, bounds.outMimeType)
    }
    override suspend fun read(path: String): ByteArray = withContext(Dispatchers.IO) { File(path).readBytes() }
    override fun preview(path: String): Uri = Uri.fromFile(File(path))
    override fun remove(path: String) { File(path).delete() }
}
