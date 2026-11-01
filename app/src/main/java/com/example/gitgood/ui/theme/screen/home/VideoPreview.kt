package com.example.gitgood.ui.theme.screen.home

import android.net.Uri
import android.widget.MediaController
import android.widget.VideoView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.gitgood.ui.theme.PrimaryGreen
import com.example.gitgood.ui.theme.SecondaryTextColor

/** Local preview only. Video bytes are never sent to the image-only API. */
@Composable
internal fun VideoPreview(uri: Uri, modifier: Modifier = Modifier) {
    var loading by remember(uri) { mutableStateOf(true) }
    var failed by remember(uri) { mutableStateOf(false) }
    val player = remember { arrayOfNulls<VideoView>(1) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_PAUSE) player[0]?.pause()
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            player[0]?.pause()
        }
    }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (failed) {
            Box(Modifier.fillMaxWidth().height(200.dp).padding(20.dp), contentAlignment = Alignment.Center) {
                Text("This video could not be played. Try a different video or choose a photo.", color = SecondaryTextColor)
            }
        } else {
            Box(Modifier.fillMaxWidth().height(240.dp), contentAlignment = Alignment.Center) {
                // Key the player by attachment so a previous video's callbacks cannot
                // change the loading/error state of the newly selected video.
                key(uri) {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = { context ->
                            VideoView(context).apply {
                                player[0] = this
                                val controls = MediaController(context)
                                controls.setAnchorView(this)
                                setMediaController(controls)
                                setOnPreparedListener {
                                    loading = false
                                    seekTo(1) // Display an initial frame without autoplaying audio.
                                    controls.show()
                                }
                                setOnErrorListener { _, _, _ ->
                                    loading = false
                                    failed = true
                                    true // Use inline feedback instead of the platform error dialog.
                                }
                                try { setVideoURI(uri) }
                                catch (_: Exception) { loading = false; failed = true }
                            }
                        },
                        onRelease = { view ->
                            view.setOnPreparedListener(null)
                            view.setOnErrorListener(null)
                            view.setMediaController(null)
                            view.stopPlayback()
                            if (player[0] === view) player[0] = null
                        }
                    )
                }
                if (loading) CircularProgressIndicator(color = PrimaryGreen)
            }
            Text("Video preview · Tap the video for playback controls", Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                fontSize = 12.sp, color = SecondaryTextColor)
        }
    }
}
