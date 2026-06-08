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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsRecordCountItem
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.EditableSessionButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingIconButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.SHOW_MORE_MAX_COUNT
import com.example.vinyllistenapp.ui.components.ShowMoreActionButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

private const val VIEW_ALL_PAGE_SIZE = 10

@Composable
fun RecentSessionsScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
    onEditSession: (String) -> Unit,
) {
    var sessions by remember { mutableStateOf(emptyList<ListeningSession>()) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getHomeSummary(recentLimit = SHOW_MORE_MAX_COUNT, topLimit = 5) }
            .onSuccess {
                sessions = it.recentSessions.take(SHOW_MORE_MAX_COUNT)
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
        PaginatedViewAllItems(items = sessions) { session ->
            SessionListItem(
                session = session,
                onClick = { onOpenRecord(session.releaseId) },
                onEditSession = { sessionId -> onEditSession(sessionId) },
            )
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
        runCatching { apiClient.getAnalyticsDashboard(topRecordsLimit = SHOW_MORE_MAX_COUNT) }
            .onSuccess {
                records = it.topRecords.take(SHOW_MORE_MAX_COUNT)
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
        PaginatedViewAllItems(items = records) { record ->
            TopRecordListItem(
                record = record,
                onClick = { onOpenRecord(record.record.releaseId) },
            )
        }
    }
}

@Composable
fun MoodDistributionScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenMoodRecords: (String) -> Unit,
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
        MoodDistributionCard(moods = moods, onMoodClick = onOpenMoodRecords)
    }
}

@Composable
fun StyleDistributionScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenStyleRecords: (String) -> Unit,
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
        StyleDistributionCard(styles = styles, onStyleClick = onOpenStyleRecords)
    }
}

@Composable
fun MonthSessionsDrilldownScreen(
    apiClient: VinylApiClient,
    month: String,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    var subtitle by remember(month) { mutableStateOf("Logged listens") }
    BackendPagedDrilldownScreen(
        title = "${analyticsMonthTitle(month)} Sessions",
        subtitle = subtitle,
        onBack = onBack,
        emptyText = "No sessions for this month.",
        loadPage = { limit, offset ->
            val page = apiClient.getAnalyticsSessionsForMonth(month = month, limit = limit, offset = offset)
            subtitle = loggedListenCountLabel(page.pagination.total)
            DrilldownPage(items = page.sessions, hasMore = page.pagination.hasMore)
        },
    ) { session ->
        SessionListItem(
            session = session,
            onClick = { onOpenRecord(session.releaseId) },
        )
    }
}

@Composable
fun RatingRecordsDrilldownScreen(
    apiClient: VinylApiClient,
    rating: Int,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    BackendPagedDrilldownScreen(
        title = "$rating Star Records",
        subtitle = "Records logged with $rating stars",
        onBack = onBack,
        emptyText = "No records for this rating.",
        loadPage = { limit, offset ->
            val page = apiClient.getAnalyticsRecordsByRating(rating = rating, limit = limit, offset = offset)
            DrilldownPage(items = page.records, hasMore = page.pagination.hasMore)
        },
    ) { item ->
        RecordCountListItem(
            item = item,
            countLabel = ratingCountLabel(item.count),
            onClick = { onOpenRecord(item.record.releaseId) },
        )
    }
}

@Composable
fun MoodRecordsDrilldownScreen(
    apiClient: VinylApiClient,
    mood: String,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    BackendPagedDrilldownScreen(
        title = mood,
        subtitle = "Records logged with this mood",
        onBack = onBack,
        emptyText = "No records for this mood.",
        loadPage = { limit, offset ->
            val page = apiClient.getAnalyticsRecordsByMood(mood = mood, limit = limit, offset = offset)
            DrilldownPage(items = page.records, hasMore = page.pagination.hasMore)
        },
    ) { item ->
        RecordCountListItem(
            item = item,
            countLabel = listenCountLabel(item.count),
            onClick = { onOpenRecord(item.record.releaseId) },
        )
    }
}

@Composable
fun StyleRecordsDrilldownScreen(
    apiClient: VinylApiClient,
    style: String,
    onBack: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    BackendPagedDrilldownScreen(
        title = style,
        subtitle = "Records with this Discogs style",
        onBack = onBack,
        emptyText = "No records for this style.",
        loadPage = { limit, offset ->
            val page = apiClient.getAnalyticsRecordsByStyle(style = style, limit = limit, offset = offset)
            DrilldownPage(items = page.records, hasMore = page.pagination.hasMore)
        },
    ) { item ->
        RecordCountListItem(
            item = item,
            countLabel = listenCountLabel(item.count),
            onClick = { onOpenRecord(item.record.releaseId) },
        )
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

private data class DrilldownPage<T>(
    val items: List<T>,
    val hasMore: Boolean,
)

@Composable
private fun <T> BackendPagedDrilldownScreen(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
    emptyText: String,
    loadPage: suspend (limit: Int, offset: Int) -> DrilldownPage<T>,
    itemContent: @Composable (T) -> Unit,
) {
    var items by remember { mutableStateOf<List<T>>(emptyList()) }
    var hasMore by remember { mutableStateOf(false) }
    var isLoadingInitial by remember { mutableStateOf(true) }
    var isLoadingMore by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    suspend fun loadFirstPage() {
        isLoadingInitial = true
        runCatching { loadPage(VIEW_ALL_PAGE_SIZE, 0) }
            .onSuccess { page ->
                items = page.items
                hasMore = page.hasMore
                error = null
            }.onFailure { failure ->
                items = emptyList()
                hasMore = false
                error = failure.toUserMessage("Could not load analytics.")
            }
        isLoadingInitial = false
    }

    fun loadMore(count: Int) {
        scope.launch {
            isLoadingMore = true
            runCatching { loadPage(count.coerceIn(1, SHOW_MORE_MAX_COUNT), items.size) }
                .onSuccess { page ->
                    items = items + page.items
                    hasMore = page.hasMore
                    error = null
                }.onFailure { failure ->
                    error = failure.toUserMessage("Could not load more analytics.")
                }
            isLoadingMore = false
        }
    }

    LaunchedEffect(title, retryKey) {
        loadFirstPage()
    }

    ViewAllScreenContent(
        title = title,
        subtitle = subtitle,
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        if (items.isEmpty() && error == null && !isLoadingInitial) {
            EmptyViewAllText(emptyText)
        }
        items.forEach { item ->
            itemContent(item)
        }
        if (hasMore) {
            ViewAllShowMoreButton(
                label = if (isLoadingMore) "Loading..." else "Show More",
                enabled = !isLoadingMore,
                onClick = { loadMore(VIEW_ALL_PAGE_SIZE) },
                onCustomCount = ::loadMore,
            )
        }
    }
}

@Composable
private fun <T> PaginatedViewAllItems(
    items: List<T>,
    itemContent: @Composable (T) -> Unit,
) {
    var visibleItemCount by rememberSaveable { mutableIntStateOf(VIEW_ALL_PAGE_SIZE) }
    LaunchedEffect(items) {
        visibleItemCount = VIEW_ALL_PAGE_SIZE
    }

    items.take(visibleItemCount).forEach { item ->
        itemContent(item)
    }

    if (visibleItemCount < items.size) {
        ViewAllShowMoreButton(
            onClick = {
                visibleItemCount = (visibleItemCount + VIEW_ALL_PAGE_SIZE).coerceAtMost(items.size)
            },
            onCustomCount = { count ->
                visibleItemCount = (visibleItemCount + count.coerceIn(1, SHOW_MORE_MAX_COUNT)).coerceAtMost(items.size)
            },
        )
    }
}

@Composable
private fun ViewAllShowMoreButton(
    onClick: () -> Unit,
    onCustomCount: (Int) -> Unit,
) {
    ViewAllShowMoreButton(
        label = "Show More",
        enabled = true,
        onClick = onClick,
        onCustomCount = onCustomCount,
    )
}

@Composable
private fun ViewAllShowMoreButton(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
    onCustomCount: (Int) -> Unit,
) {
    ShowMoreActionButton(
        label = label,
        enabled = enabled,
        onClick = onClick,
        onCustomCount = onCustomCount,
    )
}

@Composable
private fun EmptyViewAllText(text: String) {
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = text,
        color = VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun SessionListItem(
    session: ListeningSession,
    onClick: () -> Unit,
    onEditSession: ((String) -> Unit)? = null,
) {
    val editableSessionId = session.sessionId?.takeIf { session.canEdit && it.isNotBlank() && onEditSession != null }

    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Open ${session.title}", role = Role.Button, onClick = onClick),
    ) {
        Box(modifier = Modifier.fillMaxWidth()) {
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
                    Text(
                        modifier = Modifier.padding(end = if (editableSessionId != null) 40.dp else 0.dp),
                        text = session.title,
                        color = VinylColors.TextPrimary,
                        style = MaterialTheme.typography.bodyLarge,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        modifier = Modifier.padding(end = if (editableSessionId != null) 40.dp else 0.dp),
                        text = session.artist,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        SidePlayedChip(side = session.side)
                        RatingStars(
                            rating = session.rating,
                            compact = true,
                            starSize = 14.dp,
                            strokeWidth = 1.5.dp,
                        )
                        Spacer(Modifier.weight(1f))
                        Text(
                            modifier = Modifier.widthIn(min = 72.dp),
                            text = relativeLastPlayedLabel(session.playedAt),
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                            textAlign = TextAlign.End,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            editableSessionId?.let { id ->
                EditableSessionButton(
                    onClick = { onEditSession?.invoke(id) },
                    modifier = Modifier.align(Alignment.TopEnd),
                )
            }
        }
    }
}

@Composable
private fun SidePlayedChip(side: String?) {
    Text(
        modifier =
            Modifier
                .background(VinylColors.AccentGreen, VinylShapes.Chip)
                .padding(horizontal = VinylSpacing.SpaceSm, vertical = 2.dp),
        text = side?.let { "Side $it" } ?: "Side -",
        color = VinylColors.TextOnSolidAccent,
        style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp),
    )
}

@Composable
private fun RecordCountListItem(
    item: AnalyticsRecordCountItem,
    countLabel: String,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Open ${item.record.title}", role = Role.Button, onClick = onClick),
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
                imageUrl = item.record.coverImageUrl,
                contentDescription = "${item.record.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = item.record.title,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = item.record.artist,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = countLabel,
                color = VinylColors.AccentGreen,
                modifier =
                    Modifier
                        .padding(start = VinylSpacing.SpaceMd)
                        .widthIn(min = 86.dp),
                textAlign = TextAlign.End,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
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
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceXs),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
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
            }
            Spacer(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(VinylColors.BorderDefault),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                ) {
                    TopRecordMetricRow(text = "Rating: ${record.averageRating}", color = VinylColors.AccentGreen)
                    TopRecordMetricRow(text = "Top track: ${record.topTrack ?: "n/a"}", color = VinylColors.AccentOrange)
                    TopRecordMetricRow(text = "Top mood: ${record.topMood ?: "n/a"}", color = VinylColors.AccentPurple)
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
}

@Composable
private fun TopRecordMetricRow(
    text: String,
    color: Color,
) {
    Text(
        text = text,
        color = color,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        style = MaterialTheme.typography.bodySmall,
    )
}

private fun analyticsMonthTitle(month: String): String =
    runCatching {
        val parsedMonth = YearMonth.parse(month)
        val monthLabel = parsedMonth.month.getDisplayName(TextStyle.FULL, Locale.US)
        "$monthLabel ${parsedMonth.year}"
    }.getOrDefault(month)

private fun ratingCountLabel(count: Int): String = if (count == 1) "1 rating" else "$count ratings"

private fun listenCountLabel(count: Int): String = if (count == 1) "1 listen" else "$count listens"

private fun loggedListenCountLabel(count: Int): String =
    if (count == 1) {
        "1 logged listen"
    } else {
        "$count logged listens"
    }

@Composable
private fun BackText(onBack: () -> Unit) {
    Text(
        modifier = Modifier.clickable(onClickLabel = "Go back", role = Role.Button, onClick = onBack),
        text = "Back",
        color = VinylColors.AccentGreen,
    )
}
