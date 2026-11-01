package com.example.gitgood.ui.theme.screen.conversation

import android.net.Uri
import com.example.gitgood.data.model.wirereview.WireReviewState

// The sender determines the bubble's label, alignment, and color.
enum class MessageSender { USER, ASSISTANT, SYSTEM }

// One display message; its stable ID is used as the list item key.
data class ConversationMessageUi(
    val id: String,
    val sender: MessageSender,
    val text: String,
    val imageUri: Uri? = null,
    val attachmentCaption: String? = null
)

// A future ViewModel will supply this state; the screen does not mutate it.
data class ConversationUiState(
    val experimentName: String,
    val messages: List<ConversationMessageUi> = emptyList(),
    val draft: String = "",
    val isSending: Boolean = false,
    val errorMessage: String? = null,
    val isDemo: Boolean = true,
    val notice: String? = null,
    val status: String = "",
    val canSend: Boolean = true,
    val exited: Boolean = false,
    val isProcessing: Boolean = false,
    val reviewFrameUri: Uri? = null,
    val frameCaption: String? = null,
    val wireReview: WireReviewState? = null
)
