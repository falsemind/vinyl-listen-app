package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing

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

    ScreenContent(
        title = "Recent Sessions",
        subtitle = "Latest logged listens",
        topPadding = 48.dp,
        topStartContent = { BackText(onBack) },
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
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
        runCatching { apiClient.getAnalyticsDashboard(topRecordsLimit = 25) }
            .onSuccess {
                records = it.topRecords.take(25)
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load top records.")
            }
    }

    ScreenContent(
        title = "Top Records",
        subtitle = "Most played records",
        topPadding = 48.dp,
        topStartContent = { BackText(onBack) },
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        records.forEach { record ->
            TopRecordListItem(record = record, onClick = { onOpenRecord(record.record.releaseId) })
        }
        BackText(onBack)
    }
}

@Composable
fun MoodDistributionScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
) {
    var moods by remember { mutableStateOf(mockAnalyticsDashboard().moodDistribution) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getAnalyticsDashboard() }
            .onSuccess {
                moods = it.moodDistribution
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load moods.")
            }
    }

    ScreenContent(
        title = "Mood Distribution",
        subtitle = "All listening moods",
        topPadding = 48.dp,
        topStartContent = { BackText(onBack) },
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        MoodDistributionCard(moods = moods)
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
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceXs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                compact = true,
                imageUrl = session.thumbnailUrl,
                contentDescription = "${session.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(session.title, color = VinylColors.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(session.artist, color = VinylColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(relativeLastPlayedLabel(session.playedAt), color = VinylColors.TextSecondary)
            }
        }
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
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceXs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                compact = true,
                imageUrl = record.record.coverImageUrl,
                contentDescription = "${record.record.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(record.record.title, color = VinylColors.TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(record.record.artist, color = VinylColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(
                text = "${record.plays} plays",
                color = VinylColors.AccentGreen,
                modifier =
                    Modifier
                        .padding(start = VinylSpacing.SpaceMd)
                        .widthIn(min = 72.dp),
                textAlign = TextAlign.End,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun BackText(onBack: () -> Unit) {
    Text(
        modifier = Modifier.clickable(onClickLabel = "Go back", role = Role.Button, onClick = onBack),
        text = "< Go Back",
        color = VinylColors.AccentGreen,
    )
}
