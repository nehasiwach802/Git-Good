package com.example.gitgood.ui.theme.screen.conversation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.gitgood.ui.theme.*

const val MAX_CHAT_MESSAGE_LENGTH = 2000

@Composable
fun ConversationScreen(
    state: ConversationUiState,
    onDraftChange: (String) -> Unit,
    onSendMessage: () -> Unit,
    onExitConversation: () -> Unit,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
    actions: @Composable () -> Unit = {}
) {
    // Remember scrolling when Compose redraws the screen.
    val listState = rememberLazyListState()
    val draftLength = state.draft.codePointCount(0, state.draft.length)
    val canSend = state.draft.isNotBlank() && draftLength <= MAX_CHAT_MESSAGE_LENGTH && !state.isSending && state.canSend

    // Move to the newest message when a message or loading row is added.
    LaunchedEffect(state.messages.size, state.isSending) {
        val rows = state.messages.size + if (state.isSending) 1 else 0
        if (rows > 0) listState.animateScrollToItem(rows - 1)
    }

    Column(
        modifier = modifier.fillMaxSize().background(BackgroundColor)
            .imePadding().padding(horizontal = 20.dp, vertical = 10.dp)
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Circuitly", Modifier.weight(1f), fontSize = 18.sp,
                fontWeight = FontWeight.SemiBold, color = PrimaryGreen)
            TextButton(onClick = onExitConversation) {
                Text("Exit conversation", color = PrimaryGreen)
            }
        }
        Text(state.experimentName, fontSize = 20.sp,
            fontWeight = FontWeight.Medium, color = PrimaryTextColor)
        Spacer(Modifier.height(12.dp))

        // Show the demo warning independently of the message contents.
        if (state.isDemo) {
            Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {
                Text("Demo mode · Replies are simulated. No circuit diagnosis is performed.",
                    Modifier.padding(12.dp), fontSize = 12.sp, lineHeight = 18.sp, color = PrimaryGreen)
            }
            Spacer(Modifier.height(12.dp))
        }

        state.notice?.let { Text(it, fontSize = 12.sp, color = PrimaryGreen) }
        if (state.status.isNotBlank()) Text(state.status, fontSize = 12.sp, color = SecondaryTextColor)
        actions()

        // Only the message area uses remaining space and scrolls.
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (state.messages.isEmpty() && !state.isSending && state.canSend) {
                item(key = "empty") {
                    Text("Your circuit image and description will appear here when you start a conversation.",
                        color = SecondaryTextColor, fontSize = 14.sp)
                }
            }
            items(state.messages, key = { "message-${it.id}" }) { message ->
                ConversationMessageBubble(message)
            }
            if (state.isSending) {
                item(key = "loading") {
                    Row(verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        CircularProgressIndicator(Modifier.size(18.dp), color = PrimaryGreen, strokeWidth = 2.dp)
                        Text(if (state.isDemo) "Preparing demo reply…" else "Waiting for a response…",
                            color = SecondaryTextColor, fontSize = 13.sp)
                    }
                }
            }
        }

        // Errors remain visible beside the retry control, above the input.
        state.errorMessage?.let { error ->
            Text(error, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
            onRetry?.let { retry -> TextButton(onClick = retry, enabled = !state.isSending) { Text("Retry") } }
        }

        Row(Modifier.fillMaxWidth().padding(top = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = state.draft,
                onValueChange = onDraftChange,
                modifier = Modifier.weight(1f),
                label = { Text("Message") },
                placeholder = { Text("Ask about your circuit") },
                minLines = 1,
                maxLines = 4,
                shape = RoundedCornerShape(14.dp),
                isError = draftLength > MAX_CHAT_MESSAGE_LENGTH,
                supportingText = { Text("$draftLength/$MAX_CHAT_MESSAGE_LENGTH") },
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Send
                ),
                keyboardActions = KeyboardActions(onSend = { if (canSend) onSendMessage() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrimaryGreen, unfocusedBorderColor = BorderColor,
                    focusedContainerColor = SurfaceColor,
                    unfocusedContainerColor = SurfaceColor,
                    cursorColor = PrimaryGreen
                )
            )
            FilledIconButton(onClick = onSendMessage, enabled = canSend,
                modifier = Modifier.size(48.dp),
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = PrimaryGreen)) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send message")
            }
        }
    }
}
