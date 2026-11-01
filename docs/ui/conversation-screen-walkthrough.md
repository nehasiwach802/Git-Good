# Conversation UI - line-by-line walkthrough

Only the UI has been added. No navigation, Continue, repository, deployed API, or real inference has been connected in this step. The required callbacks allow that work to be done separately.

Open `ConversationScreenPreview.kt` in Android Studio and select Split or Design to view the four previews. Preview Send/Exit/Retry callbacks are intentionally no-ops; interactive preview allows typing only.

## Overall structure

`ConversationUiState -> ConversationScreen -> ConversationMessageBubble`

The caller supplies immutable state and handles draft edits, sending, exit and retry. User bubbles appear right; assistant/system bubbles appear left. The list scrolls while the header and composer remain fixed. The demo banner defaults on.

## Reading the lines

Original line numbers are shown. Leading indentation is reduced in this table for readability. Imports and structural lines are included.


## ConversationUiState.kt

Path: `app/src/main/java/com/example/gitgood/ui/theme/screen/conversation/ConversationUiState.kt`

| Line | Code | Explanation |
| --- | --- | --- |

| 1 | `package com.example.gitgood.ui.theme.screen.conversation` | Places this file in the conversation UI package. |

| 2 | `[blank]` | Blank line separating sections; no runtime effect. |

| 3 | `import android.net.Uri` | Imports the Android image-address type. |

| 4 | `[blank]` | Blank line separating sections; no runtime effect. |

| 5 | `// The sender determines the bubble's label, alignment, and color.` | Comment: The sender determines the bubble's label, alignment, and color. |

| 6 | `enum class MessageSender { USER, ASSISTANT, SYSTEM }` | Defines the three sender roles used for bubble presentation. |

| 7 | `[blank]` | Blank line separating sections; no runtime effect. |

| 8 | `// One display message; its stable ID is used as the list item key.` | Comment: One display message; its stable ID is used as the list item key. |

| 9 | `data class ConversationMessageUi(` | Defines an immutable display model for one message. |

| 10 | `val id: String,` | Stable unique ID used as the scrolling-list key. |

| 11 | `val sender: MessageSender,` | Identifies whether the sender is the user, assistant or system. |

| 12 | `val text: String,` | Text displayed inside the bubble. |

| 13 | `val imageUri: Uri? = null` | Optional local image URI; null means this message has no image. |

| 14 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 15 | `[blank]` | Blank line separating sections; no runtime effect. |

| 16 | `// A future ViewModel will supply this state; the screen does not mutate it.` | Comment: A future ViewModel will supply this state; the screen does not mutate it. |

| 17 | `data class ConversationUiState(` | Defines the complete input state consumed by the screen. |

| 18 | `val experimentName: String,` | Selected experiment name shown under the header. |

| 19 | `val messages: List<ConversationMessageUi> = emptyList(),` | Ordered messages; defaults to an empty conversation. |

| 20 | `val draft: String = "",` | Current editable message text. |

| 21 | `val isSending: Boolean = false,` | True while a caller is waiting for a response. |

| 22 | `val errorMessage: String? = null,` | Optional readable failure message. |

| 23 | `val isDemo: Boolean = true` | Defaults to demo labeling until an actual backend consumer explicitly supplies live state. |

| 24 | `)` | Closes the current block/argument list, or begins its content lambda. |


## ConversationScreen.kt

Path: `app/src/main/java/com/example/gitgood/ui/theme/screen/conversation/ConversationScreen.kt`

| Line | Code | Explanation |
| --- | --- | --- |

| 1 | `package com.example.gitgood.ui.theme.screen.conversation` | Places this file in the conversation UI package. |

| 2 | `[blank]` | Blank line separating sections; no runtime effect. |

| 3 | `import androidx.compose.foundation.background` | Imports background. |

| 4 | `import androidx.compose.foundation.layout.*` | Imports Compose/app helpers from androidx.compose.foundation.layout. |

| 5 | `import androidx.compose.foundation.lazy.LazyColumn` | Imports the efficient scrolling conversation list. |

| 6 | `import androidx.compose.foundation.lazy.items` | Imports keyed list rows. |

| 7 | `import androidx.compose.foundation.lazy.rememberLazyListState` | Imports remembered list scroll position. |

| 8 | `import androidx.compose.foundation.shape.RoundedCornerShape` | Imports rounded cards and fields. |

| 9 | `import androidx.compose.foundation.text.KeyboardActions` | Imports keyboard Send handling. |

| 10 | `import androidx.compose.foundation.text.KeyboardOptions` | Imports keyboard action/capitalization configuration. |

| 11 | `import androidx.compose.material.icons.Icons` | Imports the icon collection. |

| 12 | `import androidx.compose.material.icons.automirrored.filled.Send` | Imports the Send icon. |

| 13 | `import androidx.compose.material3.*` | Imports Compose/app helpers from androidx.compose.material3. |

| 14 | `import androidx.compose.runtime.Composable` | Imports the Compose UI annotation. |

| 15 | `import androidx.compose.runtime.LaunchedEffect` | Imports an effect tied to Compose state changes. |

| 16 | `import androidx.compose.ui.Alignment` | Imports layout alignment choices. |

| 17 | `import androidx.compose.ui.Modifier` | Imports layout and appearance modifiers. |

| 18 | `import androidx.compose.ui.text.font.FontWeight` | Imports font weight choices. |

| 19 | `import androidx.compose.ui.text.input.ImeAction` | Imports keyboard action labels. |

| 20 | `import androidx.compose.ui.text.input.KeyboardCapitalization` | Imports sentence capitalization. |

| 21 | `import androidx.compose.ui.unit.dp` | Imports density-independent layout dimensions. |

| 22 | `import androidx.compose.ui.unit.sp` | Imports font-size dimensions. |

| 23 | `import com.example.gitgood.ui.theme.*` | Imports Compose/app helpers from com.example.gitgood.ui.theme. |

| 24 | `[blank]` | Blank line separating sections; no runtime effect. |

| 25 | `const val MAX_CHAT_MESSAGE_LENGTH = 2000` | Sets the message limit to 2000 Unicode code points. |

| 26 | `[blank]` | Blank line separating sections; no runtime effect. |

| 27 | `@Composable` | Marks the following function as Compose UI content. |

| 28 | `fun ConversationScreen(` | Declares the reusable stateless conversation composable. |

| 29 | `state: ConversationUiState,` | Receives the current UI state; does not fetch it from a repository. |

| 30 | `onDraftChange: (String) -> Unit,` | Caller receives each edit to the draft. |

| 31 | `onSendMessage: () -> Unit,` | Caller handles sending when this callback is invoked. |

| 32 | `onExitConversation: () -> Unit,` | Caller handles navigation/cleanup when Exit is tapped. |

| 33 | `modifier: Modifier = Modifier,` | Allows the parent to supply layout modifiers. |

| 34 | `onRetry: (() -> Unit)? = null` | Optional retry callback; absent means no Retry control is shown. |

| 35 | `) {` | Closes the current block/argument list, or begins its content lambda. |

| 36 | `// Remember scrolling when Compose redraws the screen.` | Comment: Remember scrolling when Compose redraws the screen. |

| 37 | `val listState = rememberLazyListState()` | Remembers message-list scroll position across recompositions. |

| 38 | `val draftLength = state.draft.codePointCount(0, state.draft.length)` | Counts Unicode code points, so supplementary characters are not counted twice. |

| 39 | `val canSend = state.draft.isNotBlank() && draftLength <= MAX_CHAT_MESSAGE_LENGTH && !state.isSending` | Allows Send only for nonblank text within the limit while no response is pending. |

| 40 | `[blank]` | Blank line separating sections; no runtime effect. |

| 41 | `// Move to the newest message when a message or loading row is added.` | Comment: Move to the newest message when a message or loading row is added. |

| 42 | `LaunchedEffect(state.messages.size, state.isSending) {` | Runs the scrolling effect when message count or sending state changes. |

| 43 | `val rows = state.messages.size + if (state.isSending) 1 else 0` | Counts message rows and the optional loading row. |

| 44 | `if (rows > 0) listState.animateScrollToItem(rows - 1)` | Scrolls to the final row, avoiding an invalid negative index for an empty list. |

| 45 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 46 | `[blank]` | Blank line separating sections; no runtime effect. |

| 47 | `Column(` | Starts the screen vertical layout. |

| 48 | `modifier = modifier.fillMaxSize().background(BackgroundColor)` | Fills available space and uses the auth/home background color. |

| 49 | `.imePadding().padding(horizontal = 20.dp, vertical = 10.dp)` | Moves input above the keyboard and applies screen margins. |

| 50 | `) {` | Closes the current block/argument list, or begins its content lambda. |

| 51 | `Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {` | Starts the header row. |

| 52 | `Text("Circuitly", Modifier.weight(1f), fontSize = 18.sp,` | Displays Circuitly; weight consumes space before the Exit button. |

| 53 | `fontWeight = FontWeight.SemiBold, color = PrimaryGreen)` | Applies semibold green branding. |

| 54 | `TextButton(onClick = onExitConversation) {` | Connects the header Exit control to the caller callback. |

| 55 | `Text("Exit conversation", color = PrimaryGreen)` | Sets its visible label. |

| 56 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 57 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 58 | `Text(state.experimentName, fontSize = 20.sp,` | Displays the selected experiment name. |

| 59 | `fontWeight = FontWeight.Medium, color = PrimaryTextColor)` | Uses medium weight and the primary text color. |

| 60 | `Spacer(Modifier.height(12.dp))` | Separates heading and demo banner. |

| 61 | `[blank]` | Blank line separating sections; no runtime effect. |

| 62 | `// Show the demo warning independently of the message contents.` | Comment: Show the demo warning independently of the message contents. |

| 63 | `if (state.isDemo) {` | Only shows the demo banner for demo state. |

| 64 | `Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {` | Creates a rounded light-green banner. |

| 65 | `Text("Demo mode · Replies are simulated. No circuit diagnosis is performed.",` | Clearly states that demo replies are not circuit diagnosis. |

| 66 | `Modifier.padding(12.dp), fontSize = 12.sp, lineHeight = 18.sp, color = PrimaryGreen)` | Styles and pads the demo warning. |

| 67 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 68 | `Spacer(Modifier.height(12.dp))` | Separates the warning from message history. |

| 69 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 70 | `[blank]` | Blank line separating sections; no runtime effect. |

| 71 | `// Only the message area uses remaining space and scrolls.` | Comment: Only the message area uses remaining space and scrolls. |

| 72 | `LazyColumn(` | Creates an efficient scrolling list for conversation history. |

| 73 | `state = listState,` | Attaches the remembered scroll state. |

| 74 | `modifier = Modifier.weight(1f).fillMaxWidth(),` | Gives the list remaining vertical space, keeping header/composer fixed. |

| 75 | `contentPadding = PaddingValues(vertical = 12.dp),` | Adds padding at the beginning/end of the history. |

| 76 | `verticalArrangement = Arrangement.spacedBy(12.dp)` | Adds space between message bubbles. |

| 77 | `) {` | Closes the current block/argument list, or begins its content lambda. |

| 78 | `if (state.messages.isEmpty() && !state.isSending) {` | Shows the empty state only if there are no messages and no pending response. |

| 79 | `item(key = "empty") {` | Defines a stable key for the empty-state list row. |

| 80 | `Text("Your circuit image and description will appear here when you start a conversation.",` | Explains where the initial circuit image and description will appear. |

| 81 | `color = SecondaryTextColor, fontSize = 14.sp)` | Styles the empty-state hint. |

| 82 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 83 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 84 | `items(state.messages, key = { "message-${it.id}" }) { message ->` | Creates one keyed list row per message; callers must supply unique message IDs. |

| 85 | `ConversationMessageBubble(message)` | Delegates each row to the message-bubble composable. |

| 86 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 87 | `if (state.isSending) {` | Adds the progress row while a response is pending. |

| 88 | `item(key = "loading") {` | Gives the progress row a stable distinct key. |

| 89 | `Row(verticalAlignment = Alignment.CenterVertically,` | Places spinner and status text in a horizontal row. |

| 90 | `horizontalArrangement = Arrangement.spacedBy(10.dp)) {` | Spaces progress controls apart. |

| 91 | `CircularProgressIndicator(Modifier.size(18.dp), color = PrimaryGreen, strokeWidth = 2.dp)` | Shows indeterminate progress rather than a fabricated percentage. |

| 92 | `Text(if (state.isDemo) "Preparing demo reply…" else "Waiting for a response…",` | Uses demo-specific pending text when appropriate. |

| 93 | `color = SecondaryTextColor, fontSize = 13.sp)` | Styles the pending-response message. |

| 94 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 95 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 96 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 97 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 98 | `[blank]` | Blank line separating sections; no runtime effect. |

| 99 | `// Errors remain visible beside the retry control, above the input.` | Comment: Errors remain visible beside the retry control, above the input. |

| 100 | `state.errorMessage?.let { error ->` | Renders an error only when one exists. |

| 101 | `Text(error, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)` | Displays the error using the Material error color. |

| 102 | `onRetry?.let { retry -> TextButton(onClick = retry, enabled = !state.isSending) { Text("Retry") } }` | Shows Retry only if the caller supplies it; disables it during sending. |

| 103 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 104 | `[blank]` | Blank line separating sections; no runtime effect. |

| 105 | `Row(Modifier.fillMaxWidth().padding(top = 10.dp),` | Starts the bottom message-composer row. |

| 106 | `verticalAlignment = Alignment.CenterVertically,` | Centers field and Send control vertically. |

| 107 | `horizontalArrangement = Arrangement.spacedBy(8.dp)) {` | Spaces the field from Send. |

| 108 | `OutlinedTextField(` | Creates the multiline outlined message field. |

| 109 | `value = state.draft,` | Displays the draft supplied by the caller. |

| 110 | `onValueChange = onDraftChange,` | Emits input edits through onDraftChange. |

| 111 | `modifier = Modifier.weight(1f),` | Lets the input occupy available width beside Send. |

| 112 | `label = { Text("Message") },` | Provides an accessible Message label. |

| 113 | `placeholder = { Text("Ask about your circuit") },` | Shows a hint for an empty draft. |

| 114 | `minLines = 1,` | Starts at one visible line. |

| 115 | `maxLines = 4,` | Grows to at most four visible lines before internal scrolling. |

| 116 | `shape = RoundedCornerShape(14.dp),` | Matches the rounded app input style. |

| 117 | `isError = draftLength > MAX_CHAT_MESSAGE_LENGTH,` | Marks text exceeding the limit as invalid. |

| 118 | `supportingText = { Text("$draftLength/$MAX_CHAT_MESSAGE_LENGTH") },` | Shows the current code-point count and maximum. |

| 119 | `keyboardOptions = KeyboardOptions(` | Begins keyboard configuration. |

| 120 | `capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Send` | Capitalizes sentence starts and requests a keyboard Send action. |

| 121 | `),` | Closes the current block/argument list, or begins its content lambda. |

| 122 | `keyboardActions = KeyboardActions(onSend = { if (canSend) onSendMessage() }),` | Keyboard Send follows the same validation guard as the visible button. |

| 123 | `colors = OutlinedTextFieldDefaults.colors(` | Starts the field color configuration. |

| 124 | `focusedBorderColor = PrimaryGreen, unfocusedBorderColor = BorderColor,` | Uses green for focus and the theme border otherwise. |

| 125 | `focusedContainerColor = androidx.compose.ui.graphics.Color.White,` | Keeps focused input background white. |

| 126 | `unfocusedContainerColor = androidx.compose.ui.graphics.Color.White,` | Keeps unfocused input background white. |

| 127 | `cursorColor = PrimaryGreen` | Uses the primary green cursor. |

| 128 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 129 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 130 | `FilledIconButton(onClick = onSendMessage, enabled = canSend,` | Creates the Send control and connects it to the caller; canSend controls enabled state. |

| 131 | `modifier = Modifier.size(48.dp),` | Provides a 48dp touch target. |

| 132 | `colors = IconButtonDefaults.filledIconButtonColors(containerColor = PrimaryGreen)) {` | Matches the primary green action style. |

| 133 | `Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send message")` | Adds a direction-aware Send icon and screen-reader label. |

| 134 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 135 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 136 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 137 | `}` | Closes the current block/argument list, or begins its content lambda. |


## ConversationMessageBubble.kt

Path: `app/src/main/java/com/example/gitgood/ui/theme/screen/conversation/ConversationMessageBubble.kt`

| Line | Code | Explanation |
| --- | --- | --- |

| 1 | `package com.example.gitgood.ui.theme.screen.conversation` | Places this file in the conversation UI package. |

| 2 | `[blank]` | Blank line separating sections; no runtime effect. |

| 3 | `import androidx.compose.foundation.BorderStroke` | Imports card borders. |

| 4 | `import androidx.compose.foundation.layout.*` | Imports Compose/app helpers from androidx.compose.foundation.layout. |

| 5 | `import androidx.compose.foundation.shape.RoundedCornerShape` | Imports rounded cards and fields. |

| 6 | `import androidx.compose.material3.Surface` | Imports Surface. |

| 7 | `import androidx.compose.material3.Text` | Imports Text. |

| 8 | `import androidx.compose.runtime.*` | Imports Compose/app helpers from androidx.compose.runtime. |

| 9 | `import androidx.compose.ui.Alignment` | Imports layout alignment choices. |

| 10 | `import androidx.compose.ui.Modifier` | Imports layout and appearance modifiers. |

| 11 | `import androidx.compose.ui.graphics.Color` | Imports explicit colors such as white. |

| 12 | `import androidx.compose.ui.layout.ContentScale` | Imports image fitting options. |

| 13 | `import androidx.compose.ui.text.font.FontWeight` | Imports font weight choices. |

| 14 | `import androidx.compose.ui.unit.dp` | Imports density-independent layout dimensions. |

| 15 | `import androidx.compose.ui.unit.sp` | Imports font-size dimensions. |

| 16 | `import coil3.compose.AsyncImage` | Imports Coil image loading. |

| 17 | `import com.example.gitgood.ui.theme.*` | Imports Compose/app helpers from com.example.gitgood.ui.theme. |

| 18 | `[blank]` | Blank line separating sections; no runtime effect. |

| 19 | `@Composable` | Marks the following function as Compose UI content. |

| 20 | `internal fun ConversationMessageBubble(message: ConversationMessageUi) {` | Defines an internal reusable message-bubble composable. |

| 21 | `val isUser = message.sender == MessageSender.USER` | Checks whether to apply user-specific alignment and color. |

| 22 | `val label = when (message.sender) {` | Selects the sender label. |

| 23 | `MessageSender.USER -> "You"` | User messages are labeled You. |

| 24 | `MessageSender.ASSISTANT -> "Circuitly"` | Assistant messages are labeled Circuitly. |

| 25 | `MessageSender.SYSTEM -> "Notice"` | System messages are labeled Notice. |

| 26 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 27 | `// Reset the image error when this bubble receives a different attachment.` | Comment: Reset the image error when this bubble receives a different attachment. |

| 28 | `var imageFailed by remember(message.imageUri) { mutableStateOf(false) }` | Remembers image loading failure and resets it if the image URI changes. |

| 29 | `[blank]` | Blank line separating sections; no runtime effect. |

| 30 | `Box(Modifier.fillMaxWidth()) {` | Creates a full-width parent so the bubble can align left or right. |

| 31 | `Surface(` | Creates the message card. |

| 32 | `modifier = Modifier.fillMaxWidth(0.9f).align(if (isUser) Alignment.CenterEnd else Alignment.CenterStart),` | Uses 90 percent of the width; user aligns right, others left. |

| 33 | `shape = RoundedCornerShape(16.dp),` | Rounds bubble corners by 16dp. |

| 34 | `color = if (isUser) LightGreen else Color.White,` | Uses light green for user messages and white for other senders. |

| 35 | `border = BorderStroke(1.dp, BorderColor)` | Adds a subtle border matching the app theme. |

| 36 | `) {` | Closes the current block/argument list, or begins its content lambda. |

| 37 | `Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {` | Stacks sender, attachment and text with internal padding. |

| 38 | `Text(label, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = PrimaryGreen)` | Displays the sender label. |

| 39 | `message.imageUri?.let { uri ->` | Only renders attachment content for a non-null image URI. |

| 40 | `if (imageFailed) {` | Chooses readable fallback text after an image-loading error. |

| 41 | `Text("This image could not be displayed.", fontSize = 13.sp, color = SecondaryTextColor)` | Shows a clear image-failure message instead of an unexplained blank. |

| 42 | `} else {` | Uses normal image rendering until a load error occurs. |

| 43 | `AsyncImage(` | Creates Coil asynchronous image rendering. |

| 44 | `model = uri,` | Supplies the local image URI. |

| 45 | `contentDescription = "Circuit image attached to this message",` | Provides an accessibility description for the attachment. |

| 46 | `modifier = Modifier.fillMaxWidth().height(180.dp),` | Uses a full-width 180dp-high image area. |

| 47 | `contentScale = ContentScale.Fit,` | Fits the entire image rather than cropping circuit details. |

| 48 | `onError = { imageFailed = true }` | Switches this bubble to fallback text if Coil cannot load the image. |

| 49 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 50 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 51 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 52 | `if (message.text.isNotBlank()) {` | Avoids a blank text widget for an image-only message. |

| 53 | `Text(message.text, fontSize = 14.sp, lineHeight = 21.sp, color = PrimaryTextColor)` | Displays message text with readable body size and line spacing. |

| 54 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 55 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 56 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 57 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 58 | `}` | Closes the current block/argument list, or begins its content lambda. |


## ConversationScreenPreview.kt

Path: `app/src/main/java/com/example/gitgood/ui/theme/screen/conversation/ConversationScreenPreview.kt`

| Line | Code | Explanation |
| --- | --- | --- |

| 1 | `package com.example.gitgood.ui.theme.screen.conversation` | Places this file in the conversation UI package. |

| 2 | `[blank]` | Blank line separating sections; no runtime effect. |

| 3 | `import androidx.compose.runtime.*` | Imports Compose/app helpers from androidx.compose.runtime. |

| 4 | `import androidx.compose.ui.tooling.preview.Preview` | Imports Android Studio previews. |

| 5 | `import com.example.gitgood.ui.theme.GitGoodTheme` | Imports GitGoodTheme. |

| 6 | `[blank]` | Blank line separating sections; no runtime effect. |

| 7 | `// Sample data is used only by Android Studio previews, never as a model verdict.` | Comment: Sample data is used only by Android Studio previews, never as a model verdict. |

| 8 | `private val previewMessages = listOf(` | Creates sample messages only for Android Studio preview rendering. |

| 9 | `ConversationMessageUi("user-1", MessageSender.USER, "I connected the resistor and capacitor. Can you help me review the circuit?"),` | Adds the sample user bubble. |

| 10 | `ConversationMessageUi("assistant-1", MessageSender.ASSISTANT, "[DEMO] This is a sample reply to preview the conversation layout. No circuit has been analyzed.")` | Adds a clearly labeled sample assistant reply without a correctness verdict. |

| 11 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 12 | `[blank]` | Blank line separating sections; no runtime effect. |

| 13 | `@Composable` | Marks the following function as Compose UI content. |

| 14 | `private fun ConversationPreviewContent(initialState: ConversationUiState) {` | Wraps the screen with locally editable preview state. |

| 15 | `var state by remember { mutableStateOf(initialState) }` | Retains local sample state during preview interaction. |

| 16 | `GitGoodTheme {` | Applies the actual app theme. |

| 17 | `ConversationScreen(` | Calls the real composable so the preview uses production layout code. |

| 18 | `state = state,` | Passes the sample state. |

| 19 | `onDraftChange = { state = state.copy(draft = it) },` | Allows editing the input in interactive preview. |

| 20 | `onSendMessage = {},` | Does not simulate sending or generate a backend reply in preview. |

| 21 | `onExitConversation = {},` | Does not perform navigation in preview. |

| 22 | `onRetry = if (state.errorMessage != null) ({}) else null` | Shows a no-op Retry control only for the error preview. |

| 23 | `)` | Closes the current block/argument list, or begins its content lambda. |

| 24 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 25 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 26 | `[blank]` | Blank line separating sections; no runtime effect. |

| 27 | `@Preview(name = "Conversation", showBackground = true, widthDp = 390, heightDp = 844)` | Registers this layout state as an Android Studio preview with a 390 x 844dp viewport. |

| 28 | `@Composable` | Marks the following function as Compose UI content. |

| 29 | `private fun ConversationPreview() {` | Defines the ordinary conversation preview. |

| 30 | `ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages))` | Displays both sample message bubbles. |

| 31 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 32 | `[blank]` | Blank line separating sections; no runtime effect. |

| 33 | `@Preview(name = "Empty conversation", showBackground = true, widthDp = 390, heightDp = 844)` | Registers this layout state as an Android Studio preview with a 390 x 844dp viewport. |

| 34 | `@Composable` | Marks the following function as Compose UI content. |

| 35 | `private fun EmptyConversationPreview() {` | Defines the empty-conversation preview. |

| 36 | `ConversationPreviewContent(ConversationUiState("Verification of Ohm’s Law"))` | Displays a chat with no messages. |

| 37 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 38 | `[blank]` | Blank line separating sections; no runtime effect. |

| 39 | `@Preview(name = "Waiting for reply", showBackground = true, widthDp = 390, heightDp = 844)` | Registers this layout state as an Android Studio preview with a 390 x 844dp viewport. |

| 40 | `@Composable` | Marks the following function as Compose UI content. |

| 41 | `private fun LoadingConversationPreview() {` | Defines the pending-response preview. |

| 42 | `ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages.take(1), isSending = true))` | Displays a user message followed by the loading indicator. |

| 43 | `}` | Closes the current block/argument list, or begins its content lambda. |

| 44 | `[blank]` | Blank line separating sections; no runtime effect. |

| 45 | `@Preview(name = "Conversation error", showBackground = true, widthDp = 390, heightDp = 844)` | Registers this layout state as an Android Studio preview with a 390 x 844dp viewport. |

| 46 | `@Composable` | Marks the following function as Compose UI content. |

| 47 | `private fun ErrorConversationPreview() {` | Defines the error-state preview. |

| 48 | `ConversationPreviewContent(ConversationUiState("RC Low-Pass Filter", messages = previewMessages, errorMessage = "The response could not be loaded. Please try again."))` | Displays messages plus a readable failure and Retry control. |

| 49 | `}` | Closes the current block/argument list, or begins its content lambda. |


## What comes next

Connect a conversation ViewModel to FakeSessionRepository; map snapshots/messages to ConversationUiState; wire Home Continue and Exit navigation. Structured review/measurement actions and follow-up image selection are separate UI steps. Do not hide demo status or present a simulated circuit assessment.
