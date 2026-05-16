package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.theme.VinylColors

@Composable
fun RecentSessionsScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    var sessions by remember { mutableStateOf(MockVinylData.recentSessions.take(25)) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getHomeSummary(recentLimit = 25, topLimit = 5) }
            .onSuccess {
                sessions = it.recentSessions.take(25)
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load sessions.")
            }
    }

    ScreenContent(title = "Recent Sessions", subtitle = "Latest logged listens") {
        error?.let { RetryMessage(it, onRetry = { retryKey += 1 }) }
        sessions.forEach { session ->
            SessionListItem(session = session, onClick = { onOpenRecord(session.releaseId) })
        }
        BackText(onBack)
    }
}

@Composable
fun TopRecordsScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    var records by remember {
        mutableStateOf(
            MockVinylData.topRecords.map { AnalyticsTopRecordSummary(it.record, it.plays, it.averageRating) }.take(25),
        )
    }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getAnalyticsDashboard() }
            .onSuccess {
                records = it.topRecords.take(25)
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load top records.")
            }
    }

    ScreenContent(title = "Top Records", subtitle = "Most played records") {
        error?.let { RetryMessage(it, onRetry = { retryKey += 1 }) }
        records.forEach { record ->
            TopRecordListItem(record = record, onClick = { onOpenRecord(record.record.releaseId) })
        }
        BackText(onBack)
    }
}

@Composable
private fun SessionListItem(
    session: ListeningSession,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Open ${session.title}", role = Role.Button, onClick = onClick),
    ) {
        Text(session.title, color = VinylColors.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(session.artist, color = VinylColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(relativeLastPlayedLabel(session.playedAt), color = VinylColors.TextSecondary)
    }
}

@Composable
private fun TopRecordListItem(
    record: AnalyticsTopRecordSummary,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Open ${record.record.title}", role = Role.Button, onClick = onClick),
    ) {
        Text(record.record.title, color = VinylColors.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(record.record.artist, color = VinylColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text("${record.plays} plays", color = VinylColors.AccentGreen)
    }
}

@Composable
private fun RetryMessage(
    message: String,
    onRetry: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Retry", role = Role.Button, onClick = onRetry),
        borderColor = VinylColors.AccentOrange.copy(alpha = 0.35f),
    ) {
        Text("$message Tap to retry.", color = VinylColors.AccentOrange)
    }
}

@Composable
private fun BackText(onBack: () -> Unit) {
    Text(
        modifier = Modifier.clickable(onClickLabel = "Back", role = Role.Button, onClick = onBack),
        text = "Back",
        color = VinylColors.AccentGreen,
    )
}
