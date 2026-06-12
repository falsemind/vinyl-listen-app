package com.example.vinyllistenapp.ui.screens

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ScrollState
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.FabPosition
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.data.api.CollectionSyncJobState
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.CollectionRecord
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.ActionMenuAction
import com.example.vinyllistenapp.ui.components.ActionMenuPopup
import com.example.vinyllistenapp.ui.components.ActionMenuToggle
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.FloatingIconButton
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.components.SHOW_MORE_MAX_COUNT
import com.example.vinyllistenapp.ui.components.ShowMoreActionButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

private const val COLLECTION_PAGE_SIZE = 25

@Composable
fun CollectionScreen(
    apiClient: VinylApiClient,
    onHome: () -> Unit,
    onStats: () -> Unit,
    onInsights: () -> Unit,
    onManualSearch: () -> Unit,
    onOpenRecord: (String) -> Unit,
    initialArtistFilter: String? = null,
) {
    var records by remember { mutableStateOf<List<CollectionRecord>>(emptyList()) }
    var hasMore by remember { mutableStateOf(false) }
    var isLoadingInitial by remember { mutableStateOf(true) }
    var isLoadingMore by remember { mutableStateOf(false) }
    var isSyncing by remember { mutableStateOf(false) }
    var syncMessage by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var isActionMenuOpen by remember { mutableStateOf(false) }
    var retryKey by remember { mutableIntStateOf(0) }
    var artistFilter by remember(initialArtistFilter) { mutableStateOf(initialArtistFilter?.takeIf { it.isNotBlank() }) }
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    suspend fun loadFirstPage() {
        isLoadingInitial = true
        runCatching {
            apiClient.getCollectionReleases(
                limit = COLLECTION_PAGE_SIZE,
                offset = 0,
                artist = artistFilter,
            )
        }.onSuccess { page ->
            records = page.records
            hasMore = page.hasMore
            error = null
        }.onFailure { failure ->
            records = emptyList()
            hasMore = false
            error = failure.toUserMessage("Could not load collection records.")
        }
        isLoadingInitial = false
    }

    suspend fun followCollectionSync(activeJob: CollectionSyncJobState? = null) {
        isSyncing = true
        isLoadingInitial = false
        error = null
        syncMessage = activeJob?.displayMessage() ?: "Loading..."
        runCatching {
            if (activeJob == null) {
                apiClient.syncCollection { job ->
                    syncMessage = job.displayMessage()
                }
            } else {
                apiClient.waitForCollectionSyncJob(activeJob.jobId) { job ->
                    syncMessage = job.displayMessage()
                }
            }
            syncMessage = "Loading..."
            loadFirstPage()
        }.onFailure { failure ->
            error = failure.toUserMessage("Could not sync Discogs collection.")
        }
        isSyncing = false
        syncMessage = null
    }

    suspend fun loadCollectionState() {
        isLoadingInitial = true
        error = null
        runCatching { apiClient.getActiveCollectionSyncJob() }
            .getOrNull()
            ?.let { activeJob ->
                followCollectionSync(activeJob)
                return
            }
        loadFirstPage()
    }

    LaunchedEffect(retryKey, artistFilter) {
        loadCollectionState()
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onInsights),
                        BottomNavItem("Collection", Icons.Filled.LibraryMusic, selected = true, onClick = {}),
                    ),
            )
        },
        floatingActionButton = {
            if (records.isNotEmpty()) {
                CollectionFloatingActions(
                    showScrollToTop = scrollState.value > 0,
                    onScrollToTop = {
                        scope.launch {
                            scrollState.animateScrollTo(0)
                        }
                    },
                    onManualSearch = onManualSearch,
                    modifier =
                        Modifier.padding(
                            end = VinylSpacing.SpaceMd,
                            bottom = VinylSpacing.SpaceLg,
                        ),
                )
            }
        },
        floatingActionButtonPosition = FabPosition.End,
    ) { innerPadding ->
        val hasArtistFilter = artistFilter != null
        val showEmptyLoad = records.isEmpty() && error == null && !isLoadingInitial && !isSyncing && !hasArtistFilter
        val showCenteredStatus = records.isEmpty() && !showEmptyLoad
        if ((showEmptyLoad || showCenteredStatus) && !hasArtistFilter) {
            Box(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .background(VinylColors.AppBackground)
                        .padding(innerPadding)
                        .padding(horizontal = VinylSpacing.SpaceMd),
                contentAlignment = Alignment.Center,
            ) {
                LocalTimedSessionBanner.current?.let { banner ->
                    Column(
                        modifier =
                            Modifier
                                .align(Alignment.TopCenter)
                                .fillMaxWidth()
                                .padding(top = VinylSpacing.Space2Xl),
                    ) {
                        banner()
                    }
                }
                when {
                    showEmptyLoad ->
                        CollectionTextActionButton(
                            label = "Load Discogs Collection",
                            enabled = true,
                            onClick = { scope.launch { followCollectionSync() } },
                        )

                    else ->
                        CollectionCenteredStatus(
                            message = error ?: syncMessage ?: "Loading...",
                            isLoading = isSyncing || isLoadingInitial,
                            isError = error != null,
                            onRetry = { scope.launch { followCollectionSync() } },
                        )
                }
            }
        } else {
            CollectionListContent(
                records = records,
                hasMore = hasMore,
                isLoadingInitial = isLoadingInitial,
                isLoadingMore = isLoadingMore,
                isSyncing = isSyncing,
                syncMessage = syncMessage,
                error = error,
                artistFilter = artistFilter,
                scrollState = scrollState,
                onOpenRecord = onOpenRecord,
                onRetry = { scope.launch { followCollectionSync() } },
                onClearArtistFilter = { artistFilter = null },
                isActionMenuOpen = isActionMenuOpen,
                onActionMenuToggle = { isActionMenuOpen = !isActionMenuOpen },
                onActionMenuDismiss = { isActionMenuOpen = false },
                onSync = {
                    scope.launch { followCollectionSync() }
                },
                onShowMore = { count ->
                    scope.launch {
                        isLoadingMore = true
                        runCatching {
                            apiClient.getCollectionReleases(
                                limit = count.coerceIn(1, SHOW_MORE_MAX_COUNT),
                                offset = records.size,
                                artist = artistFilter,
                            )
                        }.onSuccess { page ->
                            records = records + page.records
                            hasMore = page.hasMore
                            error = null
                        }.onFailure { failure ->
                            error = failure.toUserMessage("Could not load more collection records.")
                        }
                        isLoadingMore = false
                    }
                },
                modifier =
                    Modifier
                        .fillMaxSize()
                        .background(VinylColors.AppBackground)
                        .padding(innerPadding),
            )
        }
    }
}

@Composable
private fun CollectionListContent(
    records: List<CollectionRecord>,
    hasMore: Boolean,
    isLoadingInitial: Boolean,
    isLoadingMore: Boolean,
    isSyncing: Boolean,
    syncMessage: String?,
    error: String?,
    artistFilter: String?,
    scrollState: ScrollState,
    onOpenRecord: (String) -> Unit,
    onRetry: () -> Unit,
    onClearArtistFilter: () -> Unit,
    isActionMenuOpen: Boolean,
    onActionMenuToggle: () -> Unit,
    onActionMenuDismiss: () -> Unit,
    onSync: () -> Unit,
    onShowMore: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val density = LocalDensity.current
    val menuOffset =
        with(density) {
            IntOffset(
                x = -VinylSpacing.SpaceMd.roundToPx(),
                y = 104.dp.roundToPx(),
            )
        }
    val showActionMenu = records.isNotEmpty() && error == null && !isLoadingInitial

    Box(modifier = modifier) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(horizontal = VinylSpacing.SpaceMd)
                    .padding(top = VinylSpacing.Space2Xl, bottom = VinylSpacing.Space2Xl),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    modifier = Modifier.weight(1f),
                    text = "Records Collection",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.headlineLarge,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (showActionMenu) {
                    ActionMenuToggle(
                        isOpen = isActionMenuOpen,
                        onClick = onActionMenuToggle,
                    )
                }
            }
            LocalTimedSessionBanner.current?.invoke()
            artistFilter?.let { artist ->
                ArtistCollectionFilterChip(
                    artist = artist,
                    onDismiss = onClearArtistFilter,
                )
            }
            syncMessage?.let { message -> CollectionStatusText(message) }
            error?.let {
                CollectionStatusText(message = it, isError = true)
                CollectionTextActionButton(label = "Retry Load", onClick = onRetry)
            }
            if (isLoadingInitial) {
                CollectionStatusText("Loading...")
            }
            if (!isLoadingInitial && records.isEmpty() && error == null && artistFilter != null) {
                CollectionStatusText("No collection records for $artistFilter.")
            }
            records.forEach { record ->
                CollectionRecordCard(record = record, onClick = { onOpenRecord(record.releaseId) })
            }
            if (hasMore) {
                ShowMoreActionButton(
                    label = if (isLoadingMore) "Loading..." else "Show More",
                    enabled = !isLoadingMore,
                    onClick = { onShowMore(COLLECTION_PAGE_SIZE) },
                    onCustomCount = onShowMore,
                )
            }
            Spacer(Modifier.height(96.dp))
        }
        if (showActionMenu && isActionMenuOpen) {
            ActionMenuPopup(
                offset = menuOffset,
                onDismiss = onActionMenuDismiss,
            ) {
                ActionMenuAction(
                    label = if (isSyncing) "Syncing..." else "Sync Items",
                    enabled = !isSyncing,
                    onClick = onSync,
                )
            }
        }
    }
}

@Composable
private fun CollectionFloatingActions(
    showScrollToTop: Boolean,
    onScrollToTop: () -> Unit,
    onManualSearch: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.End,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        if (showScrollToTop) {
            FloatingIconButton(
                icon = Icons.Filled.KeyboardArrowUp,
                contentDescription = "Scroll to top",
                onClick = onScrollToTop,
            )
        }
        FloatingIconButton(
            icon = Icons.Filled.Search,
            contentDescription = "Search collection",
            onClick = onManualSearch,
        )
    }
}

@Composable
private fun CollectionCenteredStatus(
    message: String,
    isLoading: Boolean,
    isError: Boolean,
    onRetry: () -> Unit,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(32.dp),
    ) {
        if (isLoading) {
            CollectionProcessingSpinner()
        }
        Text(
            modifier = Modifier.width(260.dp),
            text = message,
            color = if (isError) VinylColors.AccentOrange else VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        if (isError) {
            CollectionTextActionButton(label = "Retry Load", onClick = onRetry)
        }
    }
}

@Composable
private fun CollectionTextActionButton(
    label: String,
    width: Dp = 232.dp,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Box(
        modifier = Modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            modifier =
                Modifier
                    .width(width)
                    .clickable(
                        enabled = enabled,
                        onClickLabel = label,
                        role = Role.Button,
                        onClick = onClick,
                    ).padding(vertical = VinylSpacing.SpaceSm),
            text = label,
            color = VinylColors.AccentGreen,
            textAlign = TextAlign.Center,
            style =
                MaterialTheme.typography.bodyMedium.copy(
                    fontSize = (MaterialTheme.typography.bodyMedium.fontSize.value * 1.5f).sp,
                ),
        )
    }
}

@Composable
private fun CollectionStatusText(
    message: String,
    isError: Boolean = false,
) {
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = message,
        color = if (isError) VinylColors.AccentOrange else VinylColors.TextSecondary,
        textAlign = TextAlign.Center,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun ArtistCollectionFilterChip(
    artist: String,
    onDismiss: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.AccentGreen, VinylShapes.Chip)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.75f), VinylShapes.Chip)
                .clickable(
                    onClickLabel = "Clear artist filter",
                    role = Role.Button,
                    onClick = onDismiss,
                ).padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = artist,
            color = VinylColors.TextOnAccent,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Icon(
            imageVector = Icons.Filled.Close,
            contentDescription = null,
            tint = VinylColors.TextOnAccent,
            modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
private fun CollectionProcessingSpinner() {
    val transition = rememberInfiniteTransition(label = "collection-spinner")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec =
            infiniteRepeatable(
                animation = tween(durationMillis = 900, easing = LinearEasing),
                repeatMode = RepeatMode.Restart,
            ),
        label = "collection-spinner-rotation",
    )

    Canvas(
        modifier =
            Modifier
                .size(100.dp)
                .rotate(rotation),
    ) {
        drawArc(
            color = VinylColors.AccentGreen,
            startAngle = -90f,
            sweepAngle = 285f,
            useCenter = false,
            style =
                Stroke(
                    width = 6.dp.toPx(),
                    cap = StrokeCap.Round,
                ),
        )
    }
}

@Composable
private fun CollectionRecordCard(
    record: CollectionRecord,
    onClick: () -> Unit,
) {
    AccentCard(modifier = Modifier.clickable(onClick = onClick)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                compact = true,
                imageUrl = record.thumbnailUrl,
                contentDescription = "${record.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = record.title,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = record.artist,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = collectionRecordMetadata(record),
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = record.format,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (record.styles.isNotEmpty()) {
                    Text(
                        text = record.styles.joinToString(", "),
                        color = VinylColors.AccentGreen,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

private fun collectionRecordMetadata(record: CollectionRecord): String =
    listOfNotNull(
        record.year?.toString(),
        record.label,
        record.catalogNumber,
    ).joinToString(" • ")

private fun CollectionSyncJobState.displayMessage(): String =
    message.ifBlank {
        when (step) {
            com.example.vinyllistenapp.data.api.CollectionSyncJobStep.Fetching -> "Fetching collection data"
            com.example.vinyllistenapp.data.api.CollectionSyncJobStep.Importing -> "Importing data"
            com.example.vinyllistenapp.data.api.CollectionSyncJobStep.Loading,
            com.example.vinyllistenapp.data.api.CollectionSyncJobStep.Finalizing,
            -> "Loading..."
            else -> "Syncing collection"
        }
    }
