package com.example.vinyllistenapp.ui.screens

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.AiChatExportResponse
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.FloatingIconButton
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

private val suggestedPrompts =
    listOf(
        "What are my top jungle records?",
        "Which records do I play most at night?",
        "Recommend something based on my mood history",
        "What style did I explore most this month?",
    )

private const val INTRO_MESSAGE = "Ask about your listening habits, collection patterns, moods, styles, or records."

@Composable
internal fun rememberAiInsightsScreenState(): AiInsightsScreenState = remember { AiInsightsScreenState() }

internal class AiInsightsScreenState {
    val messages = mutableStateListOf<ChatMessage>(ChatMessage.Assistant(INTRO_MESSAGE))
    var inputValue by mutableStateOf("")
    var isLoadingHistory by mutableStateOf(false)
    var hasLoadedHistory by mutableStateOf(false)
    var isTyping by mutableStateOf(false)
    var isClearingHistory by mutableStateOf(false)
    var isExportingHistory by mutableStateOf(false)
    var showClearConfirmation by mutableStateOf(false)
    var shouldFocusLoadedHistory by mutableStateOf(false)
    var conversationId by mutableStateOf<String?>(null)
}

@Composable
internal fun AiInsightsScreen(
    apiClient: VinylApiClient,
    state: AiInsightsScreenState,
    requestScope: CoroutineScope,
    onHome: () -> Unit,
    onStats: () -> Unit,
    onCollection: () -> Unit,
) {
    val context = LocalContext.current
    val chatListState = rememberLazyListState()
    val scrollShortcutScope = rememberCoroutineScope()
    val messages = state.messages
    val isInteractionEnabled =
        !state.isLoadingHistory && !state.isTyping && !state.isClearingHistory && !state.isExportingHistory
    val hasUserMessages = messages.any { it is ChatMessage.User }
    val historyActionsEnabled = isInteractionEnabled && hasUserMessages
    val showScrollToLatest by remember {
        derivedStateOf { chatListState.canScrollForward }
    }

    LaunchedEffect(Unit) {
        if (!state.hasLoadedHistory && !state.isLoadingHistory) {
            state.isLoadingHistory = true
            requestScope.launch {
                try {
                    val history = apiClient.getAiChatHistory()
                    state.conversationId = history.conversationId
                    if (history.messages.isNotEmpty() && !state.isTyping) {
                        messages.clear()
                        messages.addAll(
                            history.messages.map { message ->
                                if (message.role == "user") {
                                    ChatMessage.User(message.content)
                                } else {
                                    ChatMessage.Assistant(message.content)
                                }
                            },
                        )
                        state.shouldFocusLoadedHistory = true
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    messages.add(ChatMessage.Assistant(error.toUserMessage("Could not load AI Insights history.")))
                } finally {
                    state.isLoadingHistory = false
                    state.hasLoadedHistory = true
                }
            }
        }
    }

    LaunchedEffect(state.isLoadingHistory, state.hasLoadedHistory, state.isTyping, messages.size) {
        val hasChatContent = messages.any { it.text != INTRO_MESSAGE }
        if (!state.isLoadingHistory && state.hasLoadedHistory && hasChatContent) {
            val lastMessageIndex = suggestedPrompts.size + messages.lastIndex
            val targetIndex = if (state.isTyping) lastMessageIndex + 1 else lastMessageIndex
            chatListState.scrollToItem(targetIndex)
            state.shouldFocusLoadedHistory = false
        }
    }

    fun sendMessage(text: String) {
        val message = text.trim()
        if (message.isEmpty() || !isInteractionEnabled) return
        messages.add(ChatMessage.User(message))
        state.isTyping = true
        state.inputValue = ""
        requestScope.launch {
            try {
                val response = apiClient.chatWithAi(message = message, conversationId = state.conversationId)
                state.conversationId = response.conversationId
                messages.add(ChatMessage.Assistant(response.content))
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                messages.add(
                    ChatMessage.Assistant(
                        error.toUserMessage("Could not reach AI Insights. Check backend connection."),
                    ),
                )
            } finally {
                state.isTyping = false
            }
        }
    }

    fun clearHistory() {
        if (!historyActionsEnabled) return
        state.isClearingHistory = true
        requestScope.launch {
            try {
                val response = apiClient.clearAiChatHistory(conversationId = state.conversationId)
                state.conversationId = response.conversationId
                messages.clear()
                messages.add(ChatMessage.Assistant("Chat history cleared. $INTRO_MESSAGE"))
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                messages.add(ChatMessage.Assistant(error.toUserMessage("Could not clear AI Insights history.")))
            } finally {
                state.isClearingHistory = false
            }
        }
    }

    fun exportHistory() {
        if (!historyActionsEnabled) return
        state.isExportingHistory = true
        requestScope.launch {
            try {
                val response = apiClient.exportAiChatHistory(conversationId = state.conversationId)
                val exportIntent =
                    Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_SUBJECT, "AI Insights chat export")
                        putExtra(Intent.EXTRA_TEXT, response.toShareText())
                    }
                context.startActivity(Intent.createChooser(exportIntent, "Export AI Insights chat"))
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                messages.add(ChatMessage.Assistant(error.toUserMessage("Could not export AI Insights history.")))
            } finally {
                state.isExportingHistory = false
            }
        }
    }

    if (state.showClearConfirmation) {
        AlertDialog(
            onDismissRequest = { state.showClearConfirmation = false },
            title = { Text("Clear chat history?") },
            text = { Text("This removes the saved AI Insights chat thread from backend history.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        state.showClearConfirmation = false
                        clearHistory()
                    },
                ) {
                    Text("Clear")
                }
            },
            dismissButton = {
                TextButton(onClick = { state.showClearConfirmation = false }) {
                    Text("Cancel")
                }
            },
            containerColor = VinylColors.SurfacePrimary,
            titleContentColor = VinylColors.TextPrimary,
            textContentColor = VinylColors.TextSecondary,
        )
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                drawTopBorder = false,
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Analytics", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = true, onClick = {}),
                        BottomNavItem(
                            "Collection",
                            Icons.Filled.LibraryMusic,
                            selected = false,
                            onClick = onCollection,
                        ),
                    ),
            )
        },
    ) { innerPadding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .background(VinylColors.AppBackground)
                    .padding(top = innerPadding.calculateTopPadding())
                    .padding(horizontal = VinylSpacing.SpaceMd)
                    .padding(top = VinylSpacing.Space2Xl),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
        ) {
            InsightsHeader(
                actionsEnabled = historyActionsEnabled,
                onClearHistory = { state.showClearConfirmation = true },
                onExportHistory = ::exportHistory,
            )
            LocalTimedSessionBanner.current?.invoke()
            Box(
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth(),
            ) {
                LazyColumn(
                    state = chatListState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding =
                        PaddingValues(
                            top = VinylSpacing.SpaceXs,
                            bottom = innerPadding.calculateBottomPadding() + 104.dp,
                        ),
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                ) {
                    items(suggestedPrompts) { prompt ->
                        SuggestedPromptBubble(
                            prompt = prompt,
                            enabled = isInteractionEnabled,
                            onPromptClick = ::sendMessage,
                        )
                    }
                    items(messages) { message ->
                        ChatMessageBubble(message = message)
                    }
                    if (state.isTyping) {
                        item {
                            TypingBubble()
                        }
                    }
                    if (state.isLoadingHistory) {
                        item {
                            StatusBubble(text = "Loading history...")
                        }
                    }
                }
                ChatInputBar(
                    value = state.inputValue,
                    enabled = isInteractionEnabled,
                    onValueChange = { state.inputValue = it },
                    onSend = { sendMessage(state.inputValue) },
                    modifier =
                        Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = innerPadding.calculateBottomPadding() + VinylSpacing.SpaceLg),
                )
                if (showScrollToLatest) {
                    FloatingIconButton(
                        icon = Icons.Filled.KeyboardArrowDown,
                        contentDescription = "Scroll to latest message",
                        onClick = {
                            scrollShortcutScope.launch {
                                val lastItemIndex = chatListState.layoutInfo.totalItemsCount - 1
                                if (lastItemIndex >= 0) {
                                    chatListState.animateScrollToItem(lastItemIndex)
                                }
                            }
                        },
                        modifier =
                            Modifier
                                .align(Alignment.BottomEnd)
                                .padding(
                                    bottom = innerPadding.calculateBottomPadding() + 80.dp,
                                ),
                    )
                }
            }
        }
    }
}

@Composable
private fun InsightsHeader(
    actionsEnabled: Boolean,
    onClearHistory: () -> Unit,
    onExportHistory: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        ) {
            Text(
                text = "Insights",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "Listening patterns, moods, styles, and records",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
            InsightActionButton(
                icon = Icons.Filled.FileDownload,
                contentDescription = "Export AI Insights chat",
                enabled = actionsEnabled,
                onClick = onExportHistory,
            )
            InsightActionButton(
                icon = Icons.Filled.Delete,
                contentDescription = "Clear AI Insights chat",
                enabled = actionsEnabled,
                onClick = onClearHistory,
            )
        }
    }
}

@Composable
private fun InsightActionButton(
    icon: ImageVector,
    contentDescription: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier =
            Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape)
                .clickable(
                    enabled = enabled,
                    role = Role.Button,
                    onClickLabel = contentDescription,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = if (enabled) VinylColors.TextPrimary else VinylColors.TextSecondary,
            modifier = Modifier.size(20.dp),
        )
    }
}

@Composable
private fun SuggestedPromptBubble(
    prompt: String,
    enabled: Boolean,
    onPromptClick: (String) -> Unit,
) {
    Box(modifier = Modifier.fillMaxWidth()) {
        Box(
            modifier =
                Modifier
                    .clip(VinylShapes.Button)
                    .background(VinylColors.SurfaceSecondary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                    .clickable(
                        enabled = enabled,
                        role = Role.Button,
                        onClickLabel = prompt,
                        onClick = { onPromptClick(prompt) },
                    ).padding(
                        horizontal = VinylSpacing.SpaceMd,
                        vertical = VinylSpacing.SpaceSm,
                    ),
        ) {
            Text(
                text = prompt,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun TypingBubble() {
    StatusBubble(text = "Thinking...")
}

@Composable
private fun StatusBubble(text: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        AssistantAvatar()
        Spacer(modifier = Modifier.width(VinylSpacing.SpaceSm))
        Box(
            modifier =
                Modifier
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                    .padding(VinylSpacing.SpaceMd),
        ) {
            Text(
                text = text,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ChatMessageBubble(message: ChatMessage) {
    val isUser = message is ChatMessage.User
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (!isUser) {
            AssistantAvatar()
            Spacer(modifier = Modifier.width(VinylSpacing.SpaceSm))
        }
        Box(
            modifier =
                Modifier
                    .fillMaxWidth(0.82f)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(
                        width = 1.dp,
                        color = if (isUser) VinylColors.AccentGreen else VinylColors.AccentPurple,
                        shape = VinylShapes.Card,
                    ).padding(VinylSpacing.SpaceMd),
        ) {
            Text(
                text = message.text,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun AssistantAvatar() {
    Box(
        modifier =
            Modifier
                .size(32.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.AutoAwesome,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
            modifier = Modifier.size(18.dp),
        )
    }
}

@Composable
private fun ChatInputBar(
    value: String,
    enabled: Boolean,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            enabled = enabled,
            modifier = Modifier.weight(1f),
            placeholder = {
                Text("Ask about your collection...", color = VinylColors.TextSecondary)
            },
            singleLine = true,
            shape = VinylShapes.Button,
            colors =
                OutlinedTextFieldDefaults.colors(
                    focusedTextColor = VinylColors.TextPrimary,
                    unfocusedTextColor = VinylColors.TextPrimary,
                    cursorColor = VinylColors.AccentGreen,
                    focusedContainerColor = VinylColors.SurfacePrimary,
                    unfocusedContainerColor = VinylColors.SurfacePrimary,
                    disabledContainerColor = VinylColors.SurfacePrimary,
                    focusedBorderColor = VinylColors.GreenBorder30,
                    unfocusedBorderColor = VinylColors.BorderDefault,
                ),
        )
        Box(
            modifier =
                Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(if (value.isBlank()) VinylColors.SurfaceSecondary else VinylColors.AccentGreen)
                    .border(
                        width = 1.dp,
                        color = if (value.isBlank()) VinylColors.BorderDefault else Color.Transparent,
                        shape = CircleShape,
                    ).clickable(
                        enabled = enabled && value.isNotBlank(),
                        role = Role.Button,
                        onClickLabel = "Send message",
                        onClick = onSend,
                    ),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.Send,
                contentDescription = null,
                tint = if (value.isBlank()) VinylColors.TextSecondary else VinylColors.TextOnAccent,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

internal sealed class ChatMessage(
    val text: String,
) {
    class Assistant(
        text: String,
    ) : ChatMessage(text)

    class User(
        text: String,
    ) : ChatMessage(text)
}

private fun AiChatExportResponse.toShareText(): String =
    buildString {
        appendLine("AI Insights chat export")
        appendLine("Conversation: $conversationId")
        appendLine("Exported at: $exportedAt")
        appendLine()
        messages.forEach { message ->
            appendLine("${message.role.uppercase()}: ${message.content}")
            if (message.usedTools.isNotEmpty()) {
                appendLine("Tools: ${message.usedTools.joinToString(", ")}")
            }
            appendLine()
        }
    }
