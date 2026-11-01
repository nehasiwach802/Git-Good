package com.example.gitgood.ui.theme.screen.conversation

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import com.example.gitgood.ui.theme.*

@Composable
internal fun ConversationMessageBubble(message: ConversationMessageUi) {
    val isUser = message.sender == MessageSender.USER
    val label = when (message.sender) {
        MessageSender.USER -> "You"
        MessageSender.ASSISTANT -> "Circuitly"
        MessageSender.SYSTEM -> "Notice"
    }
    // Reset the image error when this bubble receives a different attachment.
    var imageFailed by remember(message.imageUri) { mutableStateOf(false) }

    Box(Modifier.fillMaxWidth()) {
        Surface(
            modifier = Modifier.fillMaxWidth(0.9f).align(if (isUser) Alignment.CenterEnd else Alignment.CenterStart),
            shape = RoundedCornerShape(16.dp),
            color = if (isUser) LightGreen else SurfaceColor,
            border = BorderStroke(1.dp, BorderColor)
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(label, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = PrimaryGreen)
                message.imageUri?.let { uri ->
                    if (imageFailed) {
                        Text("This image could not be displayed.", fontSize = 13.sp, color = SecondaryTextColor)
                    } else {
                        AsyncImage(
                            model = uri,
                            contentDescription = "Circuit image attached to this message",
                            modifier = Modifier.fillMaxWidth().height(180.dp),
                            contentScale = ContentScale.Fit,
                            onError = { imageFailed = true }
                        )
                    }
                }
                message.attachmentCaption?.let { Text(it, fontSize = 12.sp, color = SecondaryTextColor) }
                if (message.text.isNotBlank()) {
                    Text(message.text, fontSize = 14.sp, lineHeight = 21.sp, color = PrimaryTextColor)
                }
            }
        }
    }
}
