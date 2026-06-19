package com.example.vinyllistenapp.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Icon
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsRecordCountItem
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.SessionTrack
import com.example.vinyllistenapp.domain.TimedSessionGroup
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.EditableSessionButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingIconButton
import com.example.vinyllistenapp.ui.components.LocalActiveTimedSessionId
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.SHOW_MORE_MAX_COUNT
import com.example.vinyllistenapp.ui.components.ShowMoreActionButton
import com.example.vinyllistenapp.ui.components.timedSessionMoodDirectionLabel
import com.example.vinyllistenapp.ui.components.timedSessionStyleFocusLabel
import com.example.vinyllistenapp.ui.components.timedSessionTypeLabel
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.Instant
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

private const val VIEW_ALL_PAGE_SIZE = 10

private val TIMED_SESSION_TYPE_VALUES =
    listOf("casual_listening", "dj_set", "rediscovery", "testing_records", "background")
private val TIMED_SESSION_STYLE_VALUES = listOf("mixed", "one_style", "random")
private val TIMED_SESSION_MOOD_VALUES = listOf("steady_mood", "mood_switch", "energy_build", "cool_down")
private const val TIMED_SESSION_NOTES_MAX_LENGTH = 500

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
    var editingSessionGroup by remember { mutableStateOf<TimedSessionGroup?>(null) }
    var isSavingSessionGroup by remember { mutableStateOf(false) }
    var sessionGroupEditError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getHomeSummary(recentLimit = SHOW_MORE_MAX_COUNT, topLimit = 5) }
            .onSuccess {
                sessions = it.recentSessions.take(SHOW_MORE_MAX_COUNT)
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load sessions.")
            }
    }

    fun saveSessionGroup(
        sessionGroup: TimedSessionGroup,
        styleFocus: String,
        moodDirection: String,
        sessionType: String,
        notes: String?,
    ) {
        scope.launch {
            isSavingSessionGroup = true
            runCatching {
                apiClient.updateSessionGroup(
                    sessionGroupId = sessionGroup.id,
                    styleFocus = styleFocus,
                    moodDirection = moodDirection,
                    sessionType = sessionType,
                    notes = notes,
                )
            }.onSuccess { updated ->
                sessions =
                    sessions.map { session ->
                        if (session.sessionGroupId == updated.id) {
                            session.copy(sessionGroup = updated)
                        } else {
                            session
                        }
                    }
                editingSessionGroup = null
                sessionGroupEditError = null
            }.onFailure { failure ->
                sessionGroupEditError = failure.toUserMessage("Could not save timed session.")
            }
            isSavingSessionGroup = false
        }
    }

    ViewAllScreenContent(
        title = "Recent Sessions",
        subtitle = "Latest logged listens",
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        PaginatedViewAllItems(items = groupedRecentSessionItems(sessions)) { item ->
            RecentSessionListItemContent(
                item = item,
                onOpenRecord = onOpenRecord,
                onEditSession = onEditSession,
                editingSessionGroup = editingSessionGroup,
                isSavingSessionGroup = isSavingSessionGroup,
                sessionGroupEditError = sessionGroupEditError,
                onEditSessionGroup = { group ->
                    editingSessionGroup = group
                    sessionGroupEditError = null
                },
                onSaveSessionGroup = ::saveSessionGroup,
                onCloseSessionGroupEditor = {
                    editingSessionGroup = null
                    sessionGroupEditError = null
                },
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
    var sessions by remember { mutableStateOf(emptyList<ListeningSession>()) }
    var subtitle by remember(month) { mutableStateOf("Logged listens") }
    var hasMore by remember { mutableStateOf(false) }
    var isLoadingInitial by remember { mutableStateOf(true) }
    var isLoadingMore by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    suspend fun loadFirstPage() {
        isLoadingInitial = true
        runCatching { apiClient.getAnalyticsSessionsForMonth(month = month, limit = VIEW_ALL_PAGE_SIZE, offset = 0) }
            .onSuccess { page ->
                sessions = page.sessions
                subtitle = loggedListenCountLabel(page.pagination.total)
                hasMore = page.pagination.hasMore
                error = null
            }.onFailure { failure ->
                sessions = emptyList()
                hasMore = false
                error = failure.toUserMessage("Could not load analytics.")
            }
        isLoadingInitial = false
    }

    fun loadMore(count: Int) {
        scope.launch {
            isLoadingMore = true
            runCatching {
                apiClient.getAnalyticsSessionsForMonth(
                    month = month,
                    limit = count.coerceIn(1, SHOW_MORE_MAX_COUNT),
                    offset = sessions.size,
                )
            }.onSuccess { page ->
                sessions = sessions + page.sessions
                subtitle = loggedListenCountLabel(page.pagination.total)
                hasMore = page.pagination.hasMore
                error = null
            }.onFailure { failure ->
                error = failure.toUserMessage("Could not load more analytics.")
            }
            isLoadingMore = false
        }
    }

    LaunchedEffect(month, retryKey) {
        loadFirstPage()
    }

    ViewAllScreenContent(
        title = "${analyticsMonthTitle(month)} Sessions",
        subtitle = subtitle,
        onBack = onBack,
    ) {
        error?.let { ErrorRetryCard(message = it, onRetry = { retryKey += 1 }) }
        if (sessions.isEmpty() && error == null && !isLoadingInitial) {
            EmptyViewAllText("No sessions for this month.")
        }
        groupedRecentSessionItems(sessions).forEach { item ->
            RecentSessionListItemContent(
                item = item,
                onOpenRecord = onOpenRecord,
            )
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
            LocalTimedSessionBanner.current?.invoke()
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

private sealed interface RecentSessionListItem {
    data class Single(
        val session: ListeningSession,
    ) : RecentSessionListItem

    data class Group(
        val sessionGroupId: String,
        val sessionGroup: TimedSessionGroup?,
        val sessions: List<ListeningSession>,
    ) : RecentSessionListItem
}

private fun groupedRecentSessionItems(sessions: List<ListeningSession>): List<RecentSessionListItem> {
    val groupedSessions =
        sessions
            .filter { session -> !session.sessionGroupId.isNullOrBlank() }
            .groupBy { session -> session.sessionGroupId.orEmpty() }
    val renderedGroupIds = mutableSetOf<String>()

    return sessions.mapNotNull { session ->
        val sessionGroupId = session.sessionGroupId?.takeIf { it.isNotBlank() }
        if (sessionGroupId == null) {
            RecentSessionListItem.Single(session)
        } else if (renderedGroupIds.add(sessionGroupId)) {
            RecentSessionListItem.Group(
                sessionGroupId = sessionGroupId,
                sessionGroup = groupedSessions[sessionGroupId].orEmpty().firstNotNullOfOrNull { it.sessionGroup },
                sessions = groupedSessions[sessionGroupId].orEmpty(),
            )
        } else {
            null
        }
    }
}

@Composable
private fun RecentSessionListItemContent(
    item: RecentSessionListItem,
    onOpenRecord: (String) -> Unit,
    onEditSession: ((String) -> Unit)? = null,
    editingSessionGroup: TimedSessionGroup? = null,
    isSavingSessionGroup: Boolean = false,
    sessionGroupEditError: String? = null,
    onEditSessionGroup: ((TimedSessionGroup) -> Unit)? = null,
    onSaveSessionGroup: ((TimedSessionGroup, String, String, String, String?) -> Unit)? = null,
    onCloseSessionGroupEditor: () -> Unit = {},
) {
    when (item) {
        is RecentSessionListItem.Group ->
            TimedSessionGroupListItem(
                item = item,
                onOpenRecord = onOpenRecord,
                onEditSession = onEditSession,
                editingSessionGroup = editingSessionGroup,
                isSavingSessionGroup = isSavingSessionGroup,
                sessionGroupEditError = sessionGroupEditError,
                onEditSessionGroup = onEditSessionGroup,
                onSaveSessionGroup = onSaveSessionGroup,
                onCloseSessionGroupEditor = onCloseSessionGroupEditor,
            )

        is RecentSessionListItem.Single ->
            SessionListItem(
                session = item.session,
                onClick = { onOpenRecord(item.session.releaseId) },
                onEditSession = onEditSession,
            )
    }
}

@Composable
private fun TimedSessionGroupListItem(
    item: RecentSessionListItem.Group,
    onOpenRecord: (String) -> Unit,
    onEditSession: ((String) -> Unit)? = null,
    editingSessionGroup: TimedSessionGroup? = null,
    isSavingSessionGroup: Boolean = false,
    sessionGroupEditError: String? = null,
    onEditSessionGroup: ((TimedSessionGroup) -> Unit)? = null,
    onSaveSessionGroup: ((TimedSessionGroup, String, String, String, String?) -> Unit)? = null,
    onCloseSessionGroupEditor: () -> Unit = {},
) {
    val activeTimedSessionId = LocalActiveTimedSessionId.current
    val isActiveTimedSession = item.sessionGroupId == activeTimedSessionId
    val sessionGroup = item.sessionGroup
    val editableSessionGroup = sessionGroup?.takeIf { it.status == "completed" && it.canEdit }
    val headerDate = remember(sessionGroup, item.sessions) { timedSessionHeaderDateLabel(sessionGroup, item.sessions) }

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(VinylColors.AccentGreen.copy(alpha = 0.10f), VinylShapes.Card)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.70f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier = Modifier.weight(1f),
                text = timedSessionHeaderTypeLabel(sessionGroup?.sessionType),
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = headerDate,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (editableSessionGroup != null && onEditSessionGroup != null) {
                TimedSessionGroupEditButton(
                    onClick = { onEditSessionGroup(editableSessionGroup) },
                )
            }
        }
        TimedSessionDivider()
        TimedSessionMetadataChips(
            sessionGroup = sessionGroup,
            sessions = item.sessions,
            isActive = isActiveTimedSession,
        )
        if (editingSessionGroup?.id == item.sessionGroupId && sessionGroup != null && onSaveSessionGroup != null) {
            TimedSessionGroupEditPanel(
                sessionGroup = editingSessionGroup,
                isSaving = isSavingSessionGroup,
                errorMessage = sessionGroupEditError,
                onClose = onCloseSessionGroupEditor,
                onSave = { styleFocus, moodDirection, sessionType, notes ->
                    onSaveSessionGroup(editingSessionGroup, styleFocus, moodDirection, sessionType, notes)
                },
            )
        }
        item.sessions.forEach { session ->
            SessionListItem(
                session = session,
                borderColor = VinylColors.AccentGreen.copy(alpha = 0.72f),
                onClick = { onOpenRecord(session.releaseId) },
                onEditSession = onEditSession,
            )
        }
    }
}

@Composable
private fun TimedSessionGroupEditButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .size(34.dp)
                .clip(VinylShapes.Floating)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.55f), VinylShapes.Floating)
                .clickable(
                    onClickLabel = "Edit timed session",
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.Edit,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
            modifier = Modifier.size(17.dp),
        )
    }
}

@Composable
private fun TimedSessionDivider() {
    Box(modifier = Modifier.timedSessionDivider())
}

@Composable
private fun TimedSessionGroupEditPanel(
    sessionGroup: TimedSessionGroup,
    isSaving: Boolean,
    errorMessage: String?,
    onClose: () -> Unit,
    onSave: (styleFocus: String, moodDirection: String, sessionType: String, notes: String?) -> Unit,
) {
    var selectedSessionType by remember(sessionGroup.id) { mutableStateOf(sessionGroup.sessionType) }
    var selectedStyleFocus by remember(sessionGroup.id) { mutableStateOf(sessionGroup.styleFocus) }
    var selectedMoodDirection by remember(sessionGroup.id) { mutableStateOf(sessionGroup.moodDirection) }
    var notes by remember(sessionGroup.id) { mutableStateOf(sessionGroup.notes.orEmpty().take(TIMED_SESSION_NOTES_MAX_LENGTH)) }
    val focusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

    LaunchedEffect(sessionGroup.id) {
        focusRequester.requestFocus()
        keyboardController?.show()
    }

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .shadow(8.dp, VinylShapes.Card)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.76f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TimedSessionEditDropdown(
                selectedValue = selectedSessionType,
                options = TIMED_SESSION_TYPE_VALUES,
                labelForValue = ::timedSessionTypeLabel,
                onValueChange = { selectedSessionType = it },
                modifier = Modifier.weight(1f),
            )
            TimedSessionEditDropdown(
                selectedValue = selectedStyleFocus,
                options = TIMED_SESSION_STYLE_VALUES,
                labelForValue = ::timedSessionStyleFocusLabel,
                onValueChange = { selectedStyleFocus = it },
                modifier = Modifier.weight(1f),
            )
            TimedSessionEditDropdown(
                selectedValue = selectedMoodDirection,
                options = TIMED_SESSION_MOOD_VALUES,
                labelForValue = ::timedSessionMoodDirectionLabel,
                onValueChange = { selectedMoodDirection = it },
                modifier = Modifier.weight(1f),
            )
        }
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(104.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.55f), VinylShapes.Card)
                    .padding(VinylSpacing.SpaceMd),
        ) {
            BasicTextField(
                value = notes,
                onValueChange = { notes = it.take(TIMED_SESSION_NOTES_MAX_LENGTH) },
                modifier =
                    Modifier
                        .fillMaxSize()
                        .focusRequester(focusRequester),
                textStyle = MaterialTheme.typography.bodyMedium.copy(color = VinylColors.TextPrimary),
                cursorBrush = SolidColor(VinylColors.AccentGreen),
                decorationBox = { innerTextField ->
                    if (notes.isEmpty()) {
                        Text(
                            text = "Timed session notes...",
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    innerTextField()
                },
            )
        }
        errorMessage?.let {
            Text(
                text = it,
                color = VinylColors.AccentOrange,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TimedSessionEditIconAction(
                icon = Icons.Filled.Close,
                selected = false,
                enabled = !isSaving,
                label = "Close timed session editor",
                onClick = onClose,
            )
            Spacer(modifier = Modifier.width(VinylSpacing.SpaceSm))
            TimedSessionEditIconAction(
                icon = Icons.Filled.Check,
                selected = true,
                enabled = !isSaving,
                label = "Save timed session",
                onClick = {
                    onSave(
                        selectedStyleFocus,
                        selectedMoodDirection,
                        selectedSessionType,
                        notes.trim().takeIf { it.isNotBlank() },
                    )
                },
            )
        }
    }
}

@Composable
private fun TimedSessionEditDropdown(
    selectedValue: String,
    options: List<String>,
    labelForValue: (String) -> String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var isMenuOpen by remember { mutableStateOf(false) }
    val density = LocalDensity.current
    val arrowRotation by animateFloatAsState(
        targetValue = if (isMenuOpen) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "timedSessionEditDropdownArrow",
    )
    val controlHeight = 42.dp

    Box(modifier = modifier) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(controlHeight)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.72f), VinylShapes.Card)
                    .clickable(
                        onClickLabel = "Open ${labelForValue(selectedValue)} selector",
                        role = Role.Button,
                        onClick = { isMenuOpen = !isMenuOpen },
                    ).padding(start = VinylSpacing.SpaceSm, end = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = labelForValue(selectedValue),
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.Filled.KeyboardArrowUp,
                contentDescription = null,
                tint = VinylColors.AccentGreen,
                modifier =
                    Modifier
                        .size(20.dp)
                        .graphicsLayer { rotationZ = arrowRotation },
            )
        }
        if (isMenuOpen) {
            Popup(
                alignment = Alignment.TopStart,
                offset = IntOffset(x = 0, y = with(density) { 46.dp.roundToPx() }),
                onDismissRequest = { isMenuOpen = false },
                properties = PopupProperties(focusable = true),
            ) {
                Column(
                    modifier =
                        Modifier
                            .width(156.dp)
                            .shadow(4.dp, VinylShapes.Card)
                            .clip(VinylShapes.Card)
                            .background(VinylColors.SurfacePrimary)
                            .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.72f), VinylShapes.Card),
                ) {
                    options.forEachIndexed { index, value ->
                        TimedSessionEditDropdownOption(
                            text = labelForValue(value),
                            selected = value == selectedValue,
                            alternate = index % 2 == 0,
                            onClick = {
                                isMenuOpen = false
                                onValueChange(value)
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TimedSessionEditDropdownOption(
    text: String,
    selected: Boolean,
    alternate: Boolean,
    onClick: () -> Unit,
) {
    val rowColor = if (alternate) VinylColors.SurfacePrimary else VinylColors.SurfaceSecondary
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(rowColor)
                .clickable(
                    role = Role.RadioButton,
                    onClickLabel = "Select $text",
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceSm, vertical = VinylSpacing.SpaceXs),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier =
                Modifier
                    .size(16.dp)
                    .clip(VinylShapes.Floating)
                    .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                    .border(
                        width = 1.dp,
                        color = if (selected) VinylColors.AccentGreen else VinylColors.BorderDefault,
                        shape = VinylShapes.Floating,
                    ),
            contentAlignment = Alignment.Center,
        ) {
            if (selected) {
                Icon(
                    imageVector = Icons.Filled.Check,
                    contentDescription = null,
                    tint = VinylColors.SurfacePrimary,
                    modifier = Modifier.size(11.dp),
                )
            }
        }
        Text(
            text = text,
            color = if (selected) VinylColors.AccentGreen else VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun TimedSessionEditIconAction(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    enabled: Boolean,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .size(36.dp)
                .clip(VinylShapes.Floating)
                .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.70f), VinylShapes.Floating)
                .clickable(
                    enabled = enabled,
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = if (selected) VinylColors.TextOnAccent else VinylColors.AccentGreen,
            modifier = Modifier.size(18.dp),
        )
    }
}

@Composable
private fun TimedSessionMetadataChips(
    sessionGroup: TimedSessionGroup?,
    sessions: List<ListeningSession>,
    isActive: Boolean,
    modifier: Modifier = Modifier,
) {
    val sessionNotes = sessionGroup?.notes?.trim()?.takeIf { it.isNotBlank() }
    val tracklistText = remember(sessions) { timedSessionTracklistText(sessions) }
    var isNotesPopupOpen by remember(sessionGroup?.id, sessionNotes) { mutableStateOf(false) }
    var isTracklistPopupOpen by remember(sessionGroup?.id, tracklistText) { mutableStateOf(false) }
    val averageRating = timedSessionAverageRating(sessions)
    val topMood = timedSessionTopMood(sessions)
    val recordCount = sessions.distinctBy { it.releaseId }.size
    val timeLabel = if (isActive) "Playing..." else timedSessionDurationLabel(sessions)

    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        WrappingMetadataChipRow(
            horizontalSpacing = VinylSpacing.SpaceSm,
            verticalSpacing = VinylSpacing.SpaceSm,
        ) {
            sessionGroup?.let {
                TimedSessionMetadataChip(text = timedSessionStyleFocusLabel(it.styleFocus))
                TimedSessionMetadataChip(text = timedSessionMoodDirectionLabel(it.moodDirection))
                if (sessionNotes != null) {
                    TimedSessionFilledMetadataChip(
                        text = "Notes",
                        expanded = isNotesPopupOpen,
                        expandedLabel = "Hide timed session notes",
                        collapsedLabel = "Show timed session notes",
                        onClick = { isNotesPopupOpen = !isNotesPopupOpen },
                    )
                }
            }
            if (tracklistText.isNotBlank()) {
                TimedSessionFilledMetadataChip(
                    text = "Tracklist",
                    expanded = isTracklistPopupOpen,
                    expandedLabel = "Hide timed session tracklist",
                    collapsedLabel = "Show timed session tracklist",
                    onClick = { isTracklistPopupOpen = !isTracklistPopupOpen },
                )
            }
            TimedSessionMetadataChip(text = "Time: $timeLabel")
            TimedSessionMetadataChip(text = "$recordCount x ${if (recordCount == 1) "Record" else "Records"}")
            TimedSessionMetadataChip(text = "Rating: $averageRating")
            TimedSessionMetadataChip(text = "Mood: $topMood")
        }
        if (isNotesPopupOpen && sessionNotes != null) {
            TimedSessionNotesPopup(
                notes = sessionNotes,
                onClose = { isNotesPopupOpen = false },
            )
        }
        if (isTracklistPopupOpen && tracklistText.isNotBlank()) {
            TimedSessionTracklistPopup(
                tracklistText = tracklistText,
                onClose = { isTracklistPopupOpen = false },
            )
        }
    }
}

@Composable
private fun TimedSessionFilledMetadataChip(
    text: String,
    expanded: Boolean,
    expandedLabel: String,
    collapsedLabel: String,
    onClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.AccentGreen, VinylShapes.Chip)
                .clickable(
                    onClickLabel = if (expanded) expandedLabel else collapsedLabel,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = text,
            color = VinylColors.TextOnSolidAccent,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Icon(
            imageVector = Icons.Filled.Info,
            contentDescription = null,
            tint = VinylColors.TextOnSolidAccent,
            modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
private fun TimedSessionTracklistPopup(
    tracklistText: String,
    onClose: () -> Unit,
) {
    val context = LocalContext.current

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .shadow(8.dp, VinylShapes.Card)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.76f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier = Modifier.weight(1f),
                text = "Tracklist",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            TimedSessionCopyChip(
                onClickLabel = "Copy timed session tracklist",
                onClick = { context.copyTimedSessionText("Timed session tracklist", tracklistText) },
            )
            TimedSessionEditIconAction(
                icon = Icons.Filled.Close,
                selected = false,
                enabled = true,
                label = "Close timed session tracklist",
                onClick = onClose,
            )
        }
        Box(
            modifier = Modifier.timedSessionDivider(),
        )
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = tracklistText,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun TimedSessionCopyChip(
    onClickLabel: String,
    onClick: () -> Unit,
) {
    Text(
        modifier =
            Modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.AccentGreen, VinylShapes.Chip)
                .clickable(
                    onClickLabel = onClickLabel,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        text = "Copy",
        color = VinylColors.TextOnSolidAccent,
        style = MaterialTheme.typography.bodyMedium,
        fontWeight = FontWeight.SemiBold,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun TimedSessionNotesPopup(
    notes: String,
    onClose: () -> Unit,
) {
    val context = LocalContext.current

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .shadow(8.dp, VinylShapes.Card)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.76f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier = Modifier.weight(1f),
                text = "Session notes",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            TimedSessionCopyChip(
                onClickLabel = "Copy timed session notes",
                onClick = { context.copyTimedSessionText("Timed session notes", notes) },
            )
            TimedSessionEditIconAction(
                icon = Icons.Filled.Close,
                selected = false,
                enabled = true,
                label = "Close timed session notes",
                onClick = onClose,
            )
        }
        Box(
            modifier = Modifier.timedSessionDivider(),
        )
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = notes,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun TimedSessionMetadataChip(
    text: String,
    modifier: Modifier = Modifier,
) {
    Text(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.GreenTint20, VinylShapes.Chip)
                .border(1.dp, VinylColors.AccentGreen, VinylShapes.Chip)
                .padding(horizontal = VinylSpacing.SpaceLg, vertical = VinylSpacing.SpaceSm),
        text = text,
        color = VinylColors.AccentGreen,
        style = MaterialTheme.typography.bodyMedium,
        fontWeight = FontWeight.SemiBold,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun WrappingMetadataChipRow(
    modifier: Modifier = Modifier,
    horizontalSpacing: Dp,
    verticalSpacing: Dp,
    content: @Composable () -> Unit,
) {
    val density = LocalDensity.current
    val horizontalGap = with(density) { horizontalSpacing.roundToPx() }
    val verticalGap = with(density) { verticalSpacing.roundToPx() }

    Layout(
        modifier = modifier,
        content = content,
    ) { measurables, constraints ->
        val placeables = measurables.map { measurable -> measurable.measure(constraints.copy(minWidth = 0)) }
        val positions = mutableListOf<IntOffset>()
        val maxWidth = constraints.maxWidth
        var rowWidth = 0
        var rowHeight = 0
        var layoutWidth = 0
        var layoutHeight = 0

        placeables.forEach { placeable ->
            val nextWidth = if (rowWidth == 0) placeable.width else rowWidth + horizontalGap + placeable.width
            if (rowWidth > 0 && nextWidth > maxWidth) {
                layoutHeight += rowHeight + verticalGap
                rowWidth = 0
                rowHeight = 0
            }

            val x = if (rowWidth == 0) 0 else rowWidth + horizontalGap
            positions += IntOffset(x, layoutHeight)
            rowWidth = x + placeable.width
            rowHeight = maxOf(rowHeight, placeable.height)
            layoutWidth = maxOf(layoutWidth, rowWidth)
        }

        layoutHeight += rowHeight
        layout(
            width = layoutWidth.coerceIn(constraints.minWidth, constraints.maxWidth),
            height = layoutHeight.coerceIn(constraints.minHeight, constraints.maxHeight),
        ) {
            placeables.forEachIndexed { index, placeable ->
                val position = positions[index]
                placeable.placeRelative(position.x, position.y)
            }
        }
    }
}

@Composable
private fun SessionListItem(
    session: ListeningSession,
    onClick: () -> Unit,
    onEditSession: ((String) -> Unit)? = null,
    borderColor: Color = VinylColors.BorderDefault,
) {
    val editableSessionId = session.sessionId?.takeIf { session.canEdit && it.isNotBlank() && onEditSession != null }

    AccentCard(
        modifier = Modifier.clickable(onClickLabel = "Open ${session.title}", role = Role.Button, onClick = onClick),
        borderColor = borderColor,
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

internal fun timedSessionTracklistText(sessions: List<ListeningSession>): String =
    timedSessionTracklistEntries(sessions)
        .mapIndexed { index, entry -> "${index + 1}. $entry" }
        .joinToString(separator = "\n")

private fun timedSessionHeaderTypeLabel(sessionType: String?): String =
    when (sessionType) {
        "casual_listening" -> "Casual"
        "dj_set" -> "DJ"
        "rediscovery" -> "Rediscover"
        "testing_records" -> "Testing"
        "background" -> "Background"
        else -> "Timed session"
    }

private fun timedSessionHeaderDateLabel(
    sessionGroup: TimedSessionGroup?,
    sessions: List<ListeningSession>,
): String =
    sessionGroup?.updatedAt?.toDateLabel()
        ?: sessionGroup?.endedAt?.toDateLabel()
        ?: sessions
            .mapNotNull { session -> session.createdAt ?: session.playedAt }
            .maxByOrNull { timestamp -> parseSessionInstant(timestamp) ?: Instant.MIN }
            ?.toDateLabel()
        ?: "n/a"

private fun timedSessionTracklistEntries(sessions: List<ListeningSession>): List<String> {
    val sortedSessions =
        sessions.sortedBy { session ->
            parseSessionInstant(session.playedAt) ?: parseSessionInstant(session.createdAt) ?: Instant.MIN
        }
    return sortedSessions.flatMap { session ->
        val releaseDetails = session.timedSessionReleaseDetails()
        val sortedTracks =
            session.tracks.sortedWith(
                compareBy<SessionTrack> { it.sequence ?: Int.MAX_VALUE }
                    .thenBy { it.position },
            )

        when {
            sortedTracks.isNotEmpty() ->
                sortedTracks.map { track ->
                    listOf(
                        "${track.timedSessionArtistLabel(session)} - ${track.title.cleanTracklistValue()}",
                        releaseDetails,
                    ).mapNotNull { value -> value?.trim()?.takeIf { it.isNotBlank() } }
                        .joinToString(separator = " / ")
                }

            !session.side.isNullOrBlank() ->
                listOf(
                    listOf(
                        "${session.title.cleanTracklistValue()} - ${timedSessionSideLabel(session.side)}",
                        releaseDetails,
                    ).mapNotNull { value -> value?.trim()?.takeIf { it.isNotBlank() } }
                        .joinToString(separator = " / "),
                )

            else -> emptyList()
        }
    }
}

private fun SessionTrack.timedSessionArtistLabel(session: ListeningSession): String =
    artist.cleanTracklistValue(fallback = session.artist.cleanTracklistValue())

private fun ListeningSession.timedSessionReleaseDetails(): String? =
    listOf(
        year?.toString(),
        label,
        catalogNumber,
    ).mapNotNull { value -> value?.trim()?.takeIf { it.isNotBlank() } }
        .joinToString(separator = " / ")
        .takeIf { it.isNotBlank() }

private fun timedSessionSideLabel(side: String): String {
    val cleanSide = side.cleanTracklistValue()
    return if (cleanSide.startsWith("Side ", ignoreCase = true)) cleanSide else "Side $cleanSide"
}

private fun String?.cleanTracklistValue(fallback: String = "Unknown"): String =
    this
        ?.trim()
        ?.takeIf { it.isNotBlank() }
        ?: fallback

private fun String?.toDateLabel(): String? {
    val value = this?.trim()?.takeIf { it.length >= 10 } ?: return null
    val date = value.take(10)
    return date.takeIf { candidate ->
        candidate[4] == '-' &&
            candidate[7] == '-' &&
            candidate.take(4).all { it.isDigit() } &&
            candidate.substring(5, 7).all { it.isDigit() } &&
            candidate.substring(8, 10).all { it.isDigit() }
    }
}

private fun Modifier.timedSessionDivider(): Modifier =
    fillMaxWidth()
        .height(1.dp)
        .background(VinylColors.BorderDefault)

private fun Context.copyTimedSessionText(
    clipLabel: String,
    text: String,
) {
    val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText(clipLabel, text))
}

private fun timedSessionAverageRating(sessions: List<ListeningSession>): String {
    val ratings = sessions.mapNotNull { session -> session.rating.takeIf { it > 0 } }
    if (ratings.isEmpty()) return "n/a"
    return String.format(Locale.US, "%.1f", ratings.average())
}

private fun timedSessionTopMood(sessions: List<ListeningSession>): String =
    sessions
        .map { session -> session.mood.trim() }
        .filter { mood -> mood.isNotBlank() && !mood.equals("Unspecified", ignoreCase = true) }
        .groupingBy { mood -> mood }
        .eachCount()
        .maxWithOrNull(compareBy<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
        ?.key
        ?: "n/a"

private fun timedSessionDurationLabel(sessions: List<ListeningSession>): String {
    val instants =
        sessions
            .mapNotNull { session -> parseSessionInstant(session.createdAt) ?: parseSessionInstant(session.playedAt) }
            .sorted()
    if (instants.isEmpty()) return "n/a"

    val duration = Duration.between(instants.first(), instants.last()).coerceAtLeast(Duration.ZERO)
    val hours = duration.toHours()
    val minutes = duration.toMinutes() % 60
    return when {
        hours > 0 -> "${hours}h ${minutes}min"
        else -> "${duration.toMinutes()}min"
    }
}

private fun parseSessionInstant(value: String?): Instant? =
    value
        ?.takeIf { it.isNotBlank() && it != "Unknown date" }
        ?.let { timestamp ->
            runCatching { Instant.parse(timestamp) }.getOrNull()
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
                    TopRecordMetricRow(
                        label = "Rating: ",
                        value = record.averageRating.toString(),
                        valueColor = VinylColors.AccentGreen,
                    )
                    TopRecordMetricRow(
                        label = "Top track: ",
                        value = record.topTrack ?: "n/a",
                        valueColor = VinylColors.AccentOrange,
                    )
                    TopRecordMetricRow(
                        label = "Top mood: ",
                        value = record.topMood ?: "n/a",
                        valueColor = VinylColors.AccentPurple,
                    )
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
    label: String,
    value: String,
    valueColor: Color,
) {
    Text(
        text =
            buildAnnotatedString {
                append(label)
                pushStyle(SpanStyle(color = valueColor))
                append(value)
                pop()
            },
        color = VinylColors.TextSecondary,
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
