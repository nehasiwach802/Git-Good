package com.example.gitgood.ui.theme.screen.conversation

import androidx.compose.runtime.*
import androidx.compose.ui.tooling.preview.Preview
import com.example.gitgood.ui.theme.GitGoodTheme

// Sample data is used only by Android Studio previews, never as a model verdict.
private val previewMessages = listOf(
    ConversationMessageUi("user-1", MessageSender.USER, "I connected the resistor and capacitor. Can you help me review the circuit?"),
    ConversationMessageUi("assistant-1", MessageSender.ASSISTANT, "[DEMO] This is a sample reply to preview the conversation layout. No circuit has been analyzed.")
)

@Composable
private fun ConversationPreviewContent(initialState: ConversationUiState, darkTheme: Boolean = false) {
    var state by remember { mutableStateOf(initialState) }
    GitGoodTheme(darkTheme = darkTheme) {
        ConversationScreen(
            state = state,
            onDraftChange = { state = state.copy(draft = it) },
            onSendMessage = {},
            onExitConversation = {},
            onRetry = if (state.errorMessage != null) ({}) else null
        )
    }
}

@Preview(name = "Conversation", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun ConversationPreview() {
    ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages))
}

@Preview(name = "Empty conversation", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun EmptyConversationPreview() {
    ConversationPreviewContent(ConversationUiState("Verification of Ohm’s Law"))
}

@Preview(name = "Waiting for reply", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun LoadingConversationPreview() {
    ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages.take(1), isSending = true))
}

@Preview(name = "Conversation error", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun ErrorConversationPreview() {
    ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages, errorMessage = "The response could not be loaded. Please try again."))
}

@Preview(name = "Dark conversation", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun DarkConversationPreview() {
    ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages, isDemo = false), darkTheme = true)
}
