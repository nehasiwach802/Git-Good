package com.example.gitgood.ui.theme.screen.conversation

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.gitgood.data.model.wirereview.*
import com.example.gitgood.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Uses the same native-pixel transform for the bitmap, holes, regions and paired endpoints. */
@Composable
internal fun WireReviewCanvas(
    uri: Uri,
    state: WireReviewState,
    enabled: Boolean,
    showRegions: Boolean,
    onTap: (FramePoint) -> Unit
) {
    val context = LocalContext.current
    var failed by remember(uri, state.identity) { mutableStateOf(false) }
    val bitmap by produceState<ImageBitmap?>(null, uri, state.identity) {
        value = withContext(Dispatchers.IO) {
            try {
                val decoded = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
                if (decoded == null || decoded.width != state.identity.width || decoded.height != state.identity.height) {
                    failed = true; null
                } else decoded.asImageBitmap()
            } catch (cancel: kotlinx.coroutines.CancellationException) { throw cancel } catch (_: Exception) { failed = true; null }
        }
    }
    var transform by remember(state.identity) {
        mutableStateOf(FrameTransform(state.identity.width, state.identity.height, 0.0, 0.0))
    }
    val gridColor = PrimaryGreen.copy(alpha = .65f)
    val guideColor = MaterialTheme.colorScheme.tertiary
    val regionColor = Color(0xFFF5B850)
    val unknownColor = MaterialTheme.colorScheme.error
    val selectionColor = MaterialTheme.colorScheme.onSurface
    val surface = SurfaceColor
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (failed) Text("The frame could not be decoded at its reported dimensions. Refresh the review or use manual hole entry below.", color = MaterialTheme.colorScheme.error)
        else if (bitmap == null) LinearProgressIndicator(Modifier.fillMaxWidth())
        Canvas(Modifier.fillMaxWidth().height(340.dp).clipToBounds()
            .onSizeChanged { transform = transform.copy(viewWidth = it.width.toDouble(), viewHeight = it.height.toDouble()).constrained() }
            .semantics { contentDescription = "Circuit frame. Pinch to zoom, drag to pan. Choose Add wire, then tap its two ends. Manual hole entry is available below." }
            .pointerInput(state.identity, bitmap, enabled) {
                detectTransformGestures { centroid, pan, zoom, _ ->
                    if (bitmap != null) transform = transform.zoomAt(FramePoint(centroid.x.toDouble(), centroid.y.toDouble()), zoom.toDouble(), pan.x.toDouble(), pan.y.toDouble())
                }
            }
            .pointerInput(state.identity, bitmap, enabled) {
                detectTapGestures { point ->
                    if (enabled && bitmap != null) transform.toImage(FramePoint(point.x.toDouble(), point.y.toDouble()))?.let(onTap)
                }
            }
        ) {
            drawRect(surface)
            val image = bitmap ?: return@Canvas
            val origin = transform.toView(FramePoint(0.0, 0.0))
            val scale = (transform.fit * transform.zoom).toFloat()
            withTransform({ translate(origin.x.toFloat(), origin.y.toFloat()); scale(scale, scale, Offset.Zero) }) {
                drawImage(image)
            }
            fun point(p: FramePoint): Offset = transform.toView(p).let { Offset(it.x.toFloat(), it.y.toFloat()) }
            state.grid.holes.forEach { (_, p) -> drawCircle(gridColor, 2.2.dp.toPx(), point(p)) }
            listOf("A1", "F1").forEach { id -> state.grid.holes[id]?.let { drawCircle(regionColor, 8.dp.toPx(), point(it), style = Stroke(2.dp.toPx())) } }
            if (showRegions) state.regions.forEach { box ->
                val p = point(FramePoint(box.left, box.top)); val q = point(FramePoint(box.right, box.bottom))
                drawRect(regionColor, p, Size(q.x-p.x, q.y-p.y), style = Stroke(2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 5f))))
            }
            state.wires.forEach { wire ->
                val a = wire.a.point; val b = wire.b.point
                if (a != null && b != null) drawLine(guideColor, point(a), point(b), 2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(9f, 6f)))
                listOf(wire.a, wire.b).forEachIndexed { index, endpoint -> endpoint.point?.let { p ->
                    val center = point(p)
                    val selected = state.editing == EndpointSelection(wire.id, index)
                    if (index == 0) drawCircle(unknownColor, 6.dp.toPx(), center, style = Stroke(2.dp.toPx()))
                    else drawRect(unknownColor, center - Offset(5.dp.toPx(), 5.dp.toPx()), Size(10.dp.toPx(), 10.dp.toPx()), style = Stroke(2.dp.toPx()))
                    if (selected) drawCircle(selectionColor, 10.dp.toPx(), center, style = Stroke(2.dp.toPx()))
                } }
            }
            state.firstEnd?.point?.let { drawCircle(selectionColor, 9.dp.toPx(), point(it), style = Stroke(3.dp.toPx())) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { transform = transform.zoomAt(FramePoint(transform.viewWidth/2, transform.viewHeight/2), 1/1.4) }) { Text("−") }
            OutlinedButton(onClick = { transform = transform.zoomAt(FramePoint(transform.viewWidth/2, transform.viewHeight/2), 1.4) }) { Text("+") }
            TextButton(onClick = { transform = transform.copy(zoom = 1.0, panX = 0.0, panY = 0.0).constrained() }) { Text("Reset view") }
        }
        Text("Pinch to zoom · Drag to pan · Tap after choosing Add wire or an endpoint. Lines show pairing only, not a detected wire path.", color = SecondaryTextColor, style = MaterialTheme.typography.bodySmall)
    }
}
