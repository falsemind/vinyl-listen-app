package com.example.vinyllistenapp.ui.screens

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

private val suggestedPrompts =
    listOf(
        "What are my top jazz records?",
        "Which records do I play most at night?",
        "Recommend something based on my mood history",
        "What style did I explore most this month?",
    )

@Composable
fun AiInsightsScreen(
    apiClient: VinylApiClient,
    onHome: () -> Unit,
    onStats: () -> Unit,
    onSettings: () -> Unit,
) {
    val messages =
        remember {
            mutableStateListOf<ChatMessage>(
                ChatMessage.Assistant(
                    "Ask about your listening habits, collection patterns, moods, styles, or records.",
                ),
            )
        }
    var inputValue by remember { mutableStateOf("") }
    var isTyping by remember { mutableStateOf(false) }
    var conversationId by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        try {
            val history = apiClient.getAiChatHistory()
            conversationId = history.conversationId
            if (history.messages.isNotEmpty()) {
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
            }
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            messages.add(ChatMessage.Assistant(error.toUserMessage("Could not load AI Insights history.")))
        }
    }

    fun sendMessage(text: String) {
        val message = text.trim()
        if (message.isEmpty() || isTyping) return
        messages.add(ChatMessage.User(message))
        isTyping = true
        inputValue = ""
        scope.launch {
            try {
                val response = apiClient.chatWithAi(message = message, conversationId = conversationId)
                conversationId = response.conversationId
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
                isTyping = false
            }
        }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                drawTopBorder = false,
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = true, onClick = {}),
                        BottomNavItem("Settings", Icons.Filled.Settings, selected = false, onClick = onSettings),
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
            InsightsHeader()
            Box(
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth(),
            ) {
                LazyColumn(
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
                            enabled = !isTyping,
                            onPromptClick = ::sendMessage,
                        )
                    }
                    items(messages) { message ->
                        ChatMessageBubble(message = message)
                    }
                    if (isTyping) {
                        item {
                            TypingBubble()
                        }
                    }
                }
                ChatInputBar(
                    value = inputValue,
                    enabled = !isTyping,
                    onValueChange = { inputValue = it },
                    onSend = { sendMessage(inputValue) },
                    modifier =
                        Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = innerPadding.calculateBottomPadding() + VinylSpacing.SpaceLg),
                )
            }
        }
    }
}

@Composable
private fun InsightsHeader() {
    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs)) {
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
                text = "Thinking...",
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
                    .background(if (isUser) VinylColors.AccentGreen else VinylColors.SurfacePrimary)
                    .border(
                        width = 1.dp,
                        color = if (isUser) Color.Transparent else VinylColors.BorderDefault,
                        shape = VinylShapes.Card,
                    ).padding(VinylSpacing.SpaceMd),
        ) {
            Text(
                text = message.text,
                color = if (isUser) VinylColors.TextOnAccent else VinylColors.TextPrimary,
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

private sealed class ChatMessage(
    val text: String,
) {
    class Assistant(
        text: String,
    ) : ChatMessage(text)

    class User(
        text: String,
    ) : ChatMessage(text)
}
