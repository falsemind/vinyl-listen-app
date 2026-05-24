package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingIconButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

@Composable
fun RecentSessionsScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    var sessions by remember { mutableStateOf(emptyList<ListeningSession>()) }
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

    ViewAllScreenContent(
        title = "Recent Sessions",
        subtitle = "Latest logged listens",
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        sessions.forEach { session ->
            SessionListItem(session = session, onClick = { onOpenRecord(session.releaseId) })
        }
    }
}

@Composable
fun TopRecordsScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    var records by remember { mutableStateOf(emptyList<AnalyticsTopRecordSummary>()) }
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

    ViewAllScreenContent(
        title = "Top Records",
        subtitle = "Most played records",
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        records.forEach { record ->
            TopRecordListItem(record = record, onClick = { onOpenRecord(record.record.releaseId) })
        }
    }
}

@Composable
fun MoodDistributionScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
) {
    var moods by remember { mutableStateOf(emptyAnalyticsDashboard().moodDistribution) }
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

    ViewAllScreenContent(
        title = "Mood Distribution",
        subtitle = "All listening moods",
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        MoodDistributionCard(moods = moods)
    }
}

@Composable
fun StyleDistributionScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
) {
    var styles by remember { mutableStateOf(emptyAnalyticsDashboard().styleDistribution) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getAnalyticsDashboard() }
            .onSuccess {
                styles = it.styleDistribution
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load styles.")
            }
    }

    ViewAllScreenContent(
        title = "Style Distribution",
        subtitle = "All listened release styles",
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        StyleDistributionCard(styles = styles)
    }
}

@Composable
private fun ViewAllScreenContent(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
    content: @Composable () -> Unit,
) {
    val scrollState = rememberScrollState()
    val scope = rememberCoroutineScope()
    val headerHiddenThreshold = with(LocalDensity.current) { 120.dp.roundToPx() }
    val showScrollToTop by remember {
        derivedStateOf {
            scrollState.maxValue > 0 && scrollState.value > headerHiddenThreshold
        }
    }

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(horizontal = VinylSpacing.SpaceMd)
                    .padding(top = 48.dp, bottom = VinylSpacing.Space2Xl),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
        ) {
            Text(
                text = title,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineLarge,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = subtitle,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
            BackText(onBack)
            content()
            Spacer(Modifier.height(96.dp))
        }

        if (showScrollToTop) {
            FloatingIconButton(
                icon = Icons.Filled.KeyboardArrowUp,
                contentDescription = "Scroll to top",
                onClick = {
                    scope.launch {
                        scrollState.animateScrollTo(0)
                    }
                },
                modifier =
                    Modifier
                        .align(Alignment.BottomEnd)
                        .padding(end = VinylSpacing.SpaceXl, bottom = 104.dp),
            )
        }
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
        text = "Back",
        color = VinylColors.AccentGreen,
    )
}
