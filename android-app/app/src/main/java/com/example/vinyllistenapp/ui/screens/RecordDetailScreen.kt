package com.example.vinyllistenapp.ui.screens

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
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseTrack
import com.example.vinyllistenapp.ui.components.ActionMenuAction
import com.example.vinyllistenapp.ui.components.ActionMenuPopup
import com.example.vinyllistenapp.ui.components.ActionMenuStatus
import com.example.vinyllistenapp.ui.components.ActionMenuToggle
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.EditableSessionButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.RecordDetailAlbumArtBlock
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch
import java.util.Locale

internal const val NO_RECORD_DETAIL_DATA_MESSAGE = "No data yet for this record."

@Composable
fun RecordDetailScreen(
    releaseId: String?,
    apiClient: VinylApiClient,
    onAddSession: (String) -> Unit,
    onEditSession: (String) -> Unit,
    onBack: () -> Unit,
) {
    val fallbackRecord = MockVinylData.record(releaseId)
    var record by remember(releaseId) { mutableStateOf(fallbackRecord) }
    var sessions by remember(releaseId) { mutableStateOf<List<ListeningSession>>(emptyList()) }
    var detailError by remember(releaseId) { mutableStateOf<String?>(null) }
    var isFetchingFullRelease by remember(releaseId) { mutableStateOf(false) }
    var isActionMenuOpen by remember(releaseId) { mutableStateOf(false) }
    var isTracklistExpanded by remember(releaseId) { mutableStateOf(false) }
    var selectedNote by remember(releaseId) { mutableStateOf<RecordHistoryEntry?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    val uriHandler = LocalUriHandler.current
    val density = LocalDensity.current
    val menuOffset =
        with(density) {
            IntOffset(
                x = -VinylSpacing.SpaceMd.roundToPx(),
                y = 104.dp.roundToPx(),
            )
        }

    suspend fun fetchFullRelease(): Boolean {
        isFetchingFullRelease = true
        val fetched =
            runCatching { apiClient.refreshRelease(record.releaseId) }
                .onSuccess { refreshedRecord ->
                    record = refreshedRecord
                    detailError = null
                }.onFailure { error ->
                    detailError = error.toUserMessage("Could not fetch full release info.")
                }.isSuccess
        isFetchingFullRelease = false
        return fetched
    }

    LaunchedEffect(releaseId, retryKey) {
        releaseId?.let { id ->
            runCatching {
                record = apiClient.getRelease(id)
                sessions = apiClient.getReleaseSessions(id)
                detailError = null
            }.onFailure { error ->
                detailError = error.toUserMessage("Could not load record details. Showing local prototype data.")
            }
        }
    }

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground),
    ) {
        if (isTracklistExpanded) {
            Box(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .clickable(
                            onClickLabel = "Close tracklist",
                            role = Role.Button,
                            onClick = { isTracklistExpanded = false },
                        ),
            )
        }
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = VinylSpacing.SpaceMd)
                        .padding(top = 48.dp, bottom = VinylSpacing.SpaceLg),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    modifier = Modifier.weight(1f),
                    text = "Record Details",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.headlineLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                ActionMenuToggle(
                    isOpen = isActionMenuOpen,
                    onClick = { isActionMenuOpen = !isActionMenuOpen },
                )
            }
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = VinylSpacing.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXl),
            ) {
                detailError?.let { message ->
                    ErrorRetryCard(
                        message = message,
                        onRetry = { retryKey += 1 },
                    )
                }
                RecordDetailHeroCard(
                    record = record,
                    isFetchingFullRelease = isFetchingFullRelease,
                    isTracklistExpanded = isTracklistExpanded,
                    onTracklistExpandedChange = { isTracklistExpanded = it },
                    onGetFullRelease = {
                        scope.launch {
                            fetchFullRelease()
                        }
                    },
                )
                if (shouldShowCollectionRemovedMessage(record)) {
                    CollectionRemovedMessageCard(message = recordCollectionRemovedMessage(record))
                }
                SectionTitle("Listening Stats")
                RecordDetailStatsRow(record = record, sessions = sessions)
                SectionTitle("Mood Summary")
                if (hasRecordDetailSessionData(record.releaseId, sessions)) {
                    RecordMoodSummaryCard(moodData = recordDetailMoodData(record.releaseId, sessions))
                } else {
                    NoRecordDetailDataText()
                }
                SectionTitle("Recent Sessions")
                val historyItems = recordDetailHistory(record.releaseId, sessions).take(10)
                if (historyItems.isEmpty()) {
                    NoRecordDetailDataText()
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                        historyItems.forEach { history ->
                            RecordHistoryCard(
                                history = history,
                                onNotesClick = { selectedNote = it },
                                onEditSession = { sessionId -> onEditSession(sessionId) },
                            )
                        }
                    }
                }
                Spacer(Modifier.height(128.dp))
            }
        }
        FloatingGlassButton(
            label = "+ Add Session",
            onClick = { onAddSession(record.releaseId) },
            modifier =
                Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = VinylSpacing.SpaceXl, bottom = 104.dp),
        )
        RecordDetailGoBackButton(
            onClick = onBack,
            modifier =
                Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = VinylSpacing.SpaceXl, bottom = 104.dp),
        )
        selectedNote?.let { history ->
            SessionNotesPopup(
                history = history,
                onDismiss = { selectedNote = null },
            )
        }
        if (isActionMenuOpen) {
            ActionMenuPopup(
                offset = menuOffset,
                onDismiss = { isActionMenuOpen = false },
            ) {
                if (shouldShowGetFullReleaseAction(record)) {
                    ActionMenuAction(
                        label = if (isFetchingFullRelease) "Getting Full Release..." else "Get Full Release",
                        enabled = !isFetchingFullRelease,
                        onClick = {
                            scope.launch {
                                fetchFullRelease()
                            }
                        },
                    )
                } else if (record.hasFullDiscogsInfo) {
                    ActionMenuStatus(label = "Full Discogs release")
                }
                ActionMenuAction(
                    label = "View on Discogs",
                    onClick = {
                        isActionMenuOpen = false
                        uriHandler.openUri(discogsReleaseUrl(record.discogsReleaseId))
                    },
                )
            }
        }
    }
}

@Composable
private fun CollectionRemovedMessageCard(message: String) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.AccentOrange.copy(alpha = 0.35f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        Text(
            text = message,
            color = VinylColors.AccentOrange,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun NoRecordDetailDataText() {
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = NO_RECORD_DETAIL_DATA_MESSAGE,
        color = VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun RecordDetailHeroCard(
    record: RecordSummary,
    isFetchingFullRelease: Boolean,
    isTracklistExpanded: Boolean,
    onTracklistExpandedChange: (Boolean) -> Unit,
    onGetFullRelease: () -> Unit,
) {
    val tracklistActionLabel = if (isTracklistExpanded) "Close tracklist" else "Open tracklist"
    val arrowRotation by animateFloatAsState(
        targetValue = if (isTracklistExpanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "Tracklist arrow rotation",
    )

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        CardTopAccentLine(
            accentColor = VinylColors.AccentGreen,
            alpha = 0.40f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg)) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .then(
                            if (isTracklistExpanded) {
                                Modifier.clickable(
                                    onClickLabel = "Close tracklist",
                                    role = Role.Button,
                                    onClick = { onTracklistExpandedChange(false) },
                                )
                            } else {
                                Modifier
                            },
                        ),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RecordDetailAlbumArtBlock(
                    imageUrl = record.coverImageUrl,
                    contentDescription = "${record.title} cover art",
                )
                Spacer(Modifier.width(VinylSpacing.SpaceLg))
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
                ) {
                    Text(
                        text = record.artist,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyLarge,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = record.title,
                        color = VinylColors.TextPrimary,
                        style = MaterialTheme.typography.titleLarge,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = "${record.year?.toString() ?: "Unknown year"} - ${record.label}",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = "Cat# ${record.catalogNumber ?: matchCatalogNumber(record.releaseId, 0)}",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            RecordTracklistToggle(
                arrowRotation = arrowRotation,
                actionLabel = tracklistActionLabel,
                onClick = { onTracklistExpandedChange(!isTracklistExpanded) },
            )
            if (isTracklistExpanded) {
                Spacer(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(1.dp)
                            .background(VinylColors.BorderDefault),
                )
                RecordTracklistContent(
                    record = record,
                    isFetchingFullRelease = isFetchingFullRelease,
                    onGetFullRelease = onGetFullRelease,
                    onClose = { onTracklistExpandedChange(false) },
                )
            }
        }
    }
}

@Composable
private fun RecordTracklistToggle(
    arrowRotation: Float,
    actionLabel: String,
    onClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(
                    onClickLabel = actionLabel,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(vertical = VinylSpacing.SpaceXs),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "Tracklist",
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Icon(
            imageVector = Icons.Filled.KeyboardArrowUp,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
            modifier =
                Modifier
                    .size(28.dp)
                    .graphicsLayer { rotationZ = arrowRotation },
        )
    }
}

@Composable
private fun RecordTracklistContent(
    record: RecordSummary,
    isFetchingFullRelease: Boolean,
    onGetFullRelease: () -> Unit,
    onClose: () -> Unit,
) {
    val shouldShowRefresh = shouldShowGetFullReleaseAction(record)
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .then(
                    if (shouldShowRefresh) {
                        Modifier
                    } else {
                        Modifier.clickable(
                            onClickLabel = "Close tracklist",
                            role = Role.Button,
                            onClick = onClose,
                        )
                    },
                ),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        when {
            shouldShowRefresh ->
                Text(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .clickable(
                                enabled = !isFetchingFullRelease,
                                onClickLabel = "Get Full Release",
                                role = Role.Button,
                                onClick = onGetFullRelease,
                            ).padding(vertical = VinylSpacing.SpaceXs),
                    text = if (isFetchingFullRelease) "Getting Full Release..." else "Get Full Release",
                    color = VinylColors.AccentGreen,
                    style = MaterialTheme.typography.labelLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

            record.tracklist.isEmpty() ->
                Text(
                    text = "No tracklist available",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )

            else -> {
                record.tracklist.forEach { track ->
                    Text(
                        text = displayReleaseTrack(track),
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                releaseTotalPlayTimeText(record)?.let { totalTime ->
                    Spacer(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .height(1.dp)
                                .background(VinylColors.BorderDefault),
                    )
                    Text(
                        text = totalTime,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }
    }
}

private fun discogsReleaseUrl(discogsReleaseId: Long): String = "https://www.discogs.com/release/$discogsReleaseId"

private fun displayReleaseTrack(track: ReleaseTrack): String {
    val duration =
        track.duration
            ?.takeIf { it.isNotBlank() }
            ?.let { " $it" }
            .orEmpty()
    return "${track.position}: ${track.title}$duration"
}

internal fun releaseTotalPlayTimeText(record: RecordSummary): String? {
    if (!record.hasFullDiscogsInfo || record.tracklist.isEmpty()) {
        return null
    }
    val totalSeconds =
        record.tracklist.sumOf { track ->
            parseReleaseTrackDurationSeconds(track.duration) ?: return null
        }
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    val formattedTime =
        if (hours > 0) {
            "${hours}h ${minutes}m ${seconds}s"
        } else {
            "${minutes}m ${seconds}s"
        }
    return "Total time: $formattedTime"
}

private fun parseReleaseTrackDurationSeconds(duration: String?): Int? {
    val parts =
        duration
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?.split(":")
            ?: return null
    if (parts.size !in 2..3 || parts.any { part -> part.isBlank() || part.any { !it.isDigit() } }) {
        return null
    }
    val values = parts.map { it.toIntOrNull() ?: return null }
    if (values.drop(1).any { it !in 0..59 }) {
        return null
    }
    return when (values.size) {
        2 -> values[0] * 60 + values[1]
        3 -> values[0] * 3600 + values[1] * 60 + values[2]
        else -> null
    }
}

@Composable
private fun RecordDetailStatsRow(
    record: RecordSummary,
    sessions: List<ListeningSession>,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        RecordStatCard(
            value = recordDetailTotalPlays(record.releaseId, sessions).toString(),
            label = "Total Plays",
            accentColor = VinylColors.AccentGreen,
            modifier = Modifier.weight(1f),
        )
        RecordStatCard(
            value = recordDetailAverageRating(record.releaseId, sessions),
            label = "Avg Rating",
            accentColor = VinylColors.AccentOrange,
            modifier = Modifier.weight(1f),
        )
        RecordStatCard(
            value = recordDetailLastPlayed(record.releaseId, sessions),
            label = "Last Played",
            accentColor = VinylColors.AccentPurple,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun RecordStatCard(
    value: String,
    label: String,
    accentColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(108.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, accentColor.copy(alpha = 0.35f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
    ) {
        CardTopAccentLine(
            accentColor = accentColor,
            alpha = 0.40f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(
            modifier = Modifier.align(Alignment.CenterStart),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        ) {
            Text(
                text = value,
                color = accentColor,
                style = MaterialTheme.typography.headlineLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = label,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun RecordMoodSummaryCard(moodData: List<RecordMoodSummary>) {
    val maxCount = moodData.maxOf { it.count }.coerceAtLeast(1)

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        CardTopAccentLine(
            accentColor = VinylColors.AccentGreen,
            alpha = 0.30f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg)) {
            moodData.forEach { item ->
                RecordMoodRow(item = item, maxCount = maxCount)
            }
        }
    }
}

@Composable
private fun RecordMoodRow(
    item: RecordMoodSummary,
    maxCount: Int,
) {
    val fraction = (item.count.toFloat() / maxCount.toFloat()).coerceIn(0.05f, 1f)

    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = item.mood,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = "${item.count} plays",
                color = item.color,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(CircleShape)
                    .background(VinylColors.SurfaceSecondary),
        ) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth(fraction)
                        .height(8.dp)
                        .clip(CircleShape)
                        .background(item.color),
            )
        }
    }
}

@Composable
private fun RecordHistoryCard(
    history: RecordHistoryEntry,
    onNotesClick: (RecordHistoryEntry) -> Unit,
    onEditSession: (String) -> Unit,
) {
    val editableSessionId = history.sessionId?.takeIf { history.canEdit && it.isNotBlank() }
    val metadataLeadWidth = 156.dp
    val hasNotes = history.hasNotes && !history.notes.isNullOrBlank()

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        CardTopAccentLine(
            accentColor = VinylColors.AccentGreen,
            alpha = 0.30f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
        ) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(end = if (editableSessionId != null) 40.dp else 0.dp),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    modifier = Modifier.width(metadataLeadWidth),
                    text = history.date,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (hasNotes) {
                    Text(
                        modifier =
                            Modifier
                                .clip(VinylShapes.Chip)
                                .background(VinylColors.SurfaceSecondary)
                                .clickable { onNotesClick(history) }
                                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceXs),
                        text = "Has notes",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                    )
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    modifier =
                        Modifier
                            .width(metadataLeadWidth),
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        modifier =
                            Modifier
                                .clip(VinylShapes.Chip)
                                .background(VinylColors.AccentGreen)
                                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceXs),
                        text = "Side ${history.side}",
                        color = VinylColors.AppBackground,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                    )
                    RatingStars(
                        rating = history.rating,
                        compact = true,
                        starSize = 15.dp,
                        strokeWidth = 1.75.dp,
                    )
                }
                Text(
                    modifier = Modifier.weight(1f),
                    text = history.mood,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        editableSessionId?.let { id ->
            EditableSessionButton(
                onClick = { onEditSession(id) },
                modifier = Modifier.align(Alignment.TopEnd),
            )
        }
    }
}

@Composable
private fun SessionNotesPopup(
    history: RecordHistoryEntry,
    onDismiss: () -> Unit,
) {
    Popup(
        alignment = Alignment.Center,
        onDismissRequest = onDismiss,
        properties = PopupProperties(focusable = true),
    ) {
        Box(
            modifier =
                Modifier
                    .width(300.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.35f), VinylShapes.Card)
                    .padding(VinylSpacing.SpaceLg),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
                Text(
                    text = "Session Notes",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = history.date,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
                ScrollableSessionNoteText(note = history.notes.orEmpty())
            }
        }
    }
}

@Composable
private fun ScrollableSessionNoteText(note: String) {
    val scrollState = rememberScrollState()
    val density = LocalDensity.current
    val maxNoteHeight = with(density) { 20.sp.toDp() * 25f }
    var viewportHeightPx by remember { mutableIntStateOf(0) }

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .heightIn(max = maxNoteHeight)
                .onSizeChanged { viewportHeightPx = it.height },
    ) {
        Text(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(end = if (scrollState.maxValue > 0) VinylSpacing.SpaceMd else 0.dp)
                    .verticalScroll(scrollState),
            text = note,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium.copy(lineHeight = 20.sp),
        )
        if (scrollState.maxValue > 0 && viewportHeightPx > 0) {
            val viewportHeight = viewportHeightPx.toFloat()
            val contentHeight = viewportHeight + scrollState.maxValue
            val minThumbHeight = with(density) { 24.dp.toPx() }
            val thumbHeight = (viewportHeight * viewportHeight / contentHeight).coerceAtLeast(minThumbHeight)
            val thumbOffset =
                scrollState.value / scrollState.maxValue.toFloat() * (viewportHeight - thumbHeight)

            Box(
                modifier =
                    Modifier
                        .align(Alignment.CenterEnd)
                        .width(3.dp)
                        .fillMaxHeight()
                        .clip(CircleShape)
                        .background(VinylColors.BorderDefault.copy(alpha = 0.55f)),
            )
            Box(
                modifier =
                    Modifier
                        .align(Alignment.TopEnd)
                        .offset(y = with(density) { thumbOffset.toDp() })
                        .width(3.dp)
                        .height(with(density) { thumbHeight.toDp() })
                        .clip(CircleShape)
                        .background(VinylColors.AccentGreen),
            )
        }
    }
}

@Composable
private fun RecordDetailGoBackButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val brush =
        Brush.linearGradient(
            listOf(
                VinylColors.AccentGreen.copy(alpha = 0.85f),
                VinylColors.AccentGreen.copy(alpha = 0.70f),
            ),
        )

    Box(
        modifier =
            modifier
                .size(56.dp)
                .shadow(
                    elevation = 12.dp,
                    shape = VinylShapes.Floating,
                    ambientColor = VinylColors.ShadowBlack,
                    spotColor = VinylColors.ShadowBlack,
                ).clip(VinylShapes.Floating)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Floating)
                .clickable(
                    onClickLabel = "Go Back",
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
            contentDescription = null,
            tint = VinylColors.TextOnAccent,
            modifier = Modifier.size(24.dp),
        )
    }
}

internal data class RecordMoodSummary(
    val mood: String,
    val count: Int,
    val color: androidx.compose.ui.graphics.Color,
)

internal data class RecordHistoryEntry(
    val date: String,
    val side: String,
    val rating: Int,
    val mood: String,
    val hasNotes: Boolean,
    val notes: String?,
    val sessionId: String? = null,
    val canEdit: Boolean = false,
)

internal fun recordDetailTotalPlays(
    releaseId: String,
    sessions: List<ListeningSession>,
): Int =
    sessions.takeIf { it.isNotEmpty() }?.size
        ?: 0.takeUnless { shouldUsePrototypeRecordDetailFallback(releaseId) }
        ?: when (releaseId) {
            "release-001" -> 12
            "release-002" -> 8
            "release-003" -> 10
            else -> 6
        }

internal fun recordDetailAverageRating(
    releaseId: String,
    sessions: List<ListeningSession>,
): String =
    sessions.filter { it.rating > 0 }.takeIf { it.isNotEmpty() }?.let { ratedSessions ->
        String.format(Locale.US, "%.1f", ratedSessions.map { it.rating }.average())
    } ?: "0".takeUnless { shouldUsePrototypeRecordDetailFallback(releaseId) }
        ?: when (releaseId) {
            "release-001" -> "4.8"
            "release-002" -> "4.2"
            "release-003" -> "4.7"
            else -> "4.0"
        }

internal fun recordDetailLastPlayed(
    releaseId: String,
    sessions: List<ListeningSession>,
): String =
    sessions.firstOrNull()?.playedAt?.let(::relativeLastPlayedLabel)
        ?: "0".takeUnless { shouldUsePrototypeRecordDetailFallback(releaseId) }
        ?: when (releaseId) {
            "release-001" -> "5d ago"
            "release-002" -> "1w ago"
            "release-003" -> "2w ago"
            else -> "Recent"
        }

internal fun recordDetailMoodData(
    releaseId: String,
    sessions: List<ListeningSession>,
): List<RecordMoodSummary> {
    val colors = listOf(VinylColors.AccentGreen, VinylColors.AccentOrange, VinylColors.AccentPurple)
    val sessionMoodData =
        sessions
            .filter { it.mood.isNotBlank() }
            .groupingBy { it.mood }
            .eachCount()
            .entries
            .sortedByDescending { it.value }
            .mapIndexed { index, entry -> RecordMoodSummary(entry.key, entry.value, colors[index % colors.size]) }
    if (sessionMoodData.isNotEmpty()) return sessionMoodData
    if (!shouldUsePrototypeRecordDetailFallback(releaseId)) return emptyList()

    return when (releaseId) {
        "release-002" ->
            listOf(
                RecordMoodSummary("Late night", 4, VinylColors.AccentPurple),
                RecordMoodSummary("Focused", 3, VinylColors.AccentGreen),
                RecordMoodSummary("Calm", 2, VinylColors.AccentGreen),
                RecordMoodSummary("Social", 1, VinylColors.AccentOrange),
                RecordMoodSummary("Background", 1, VinylColors.AccentPurple),
            )

        "release-003" ->
            listOf(
                RecordMoodSummary("Calm", 4, VinylColors.AccentGreen),
                RecordMoodSummary("Nostalgic", 4, VinylColors.AccentPurple),
                RecordMoodSummary("Relaxed", 2, VinylColors.AccentOrange),
                RecordMoodSummary("Focused", 2, VinylColors.AccentGreen),
                RecordMoodSummary("Melancholic", 1, VinylColors.AccentPurple),
            )

        else ->
            listOf(
                RecordMoodSummary("Calm", 5, VinylColors.AccentGreen),
                RecordMoodSummary("Focused", 3, VinylColors.AccentOrange),
                RecordMoodSummary("Nostalgic", 2, VinylColors.AccentPurple),
                RecordMoodSummary("Energetic", 2, VinylColors.AccentOrange),
                RecordMoodSummary("Background", 1, VinylColors.AccentGreen),
            )
    }
}

internal fun recordDetailHistory(
    releaseId: String,
    sessions: List<ListeningSession>,
): List<RecordHistoryEntry> {
    val sessionHistory =
        sessions.map { session ->
            val notes = session.notes?.trim()?.takeIf { it.isNotEmpty() }
            RecordHistoryEntry(
                date = absolutePlayedDateLabel(session.playedAt),
                side = session.side?.removePrefix("Side ") ?: "-",
                rating = session.rating,
                mood = session.mood,
                hasNotes = session.hasNotes || notes != null,
                notes = notes,
                sessionId = session.sessionId,
                canEdit = session.canEdit,
            )
        }
    if (sessionHistory.isNotEmpty()) return sessionHistory
    if (!shouldUsePrototypeRecordDetailFallback(releaseId)) return emptyList()

    return when (releaseId) {
        "release-002" ->
            listOf(
                RecordHistoryEntry(
                    "2026-04-25",
                    "A",
                    4,
                    "Late night",
                    true,
                    "Warm late-night listen with a clean low end.",
                ),
                RecordHistoryEntry("2026-04-18", "B", 4, "Focused", false, null),
                RecordHistoryEntry(
                    "2026-04-03",
                    "A",
                    5,
                    "Social",
                    true,
                    "Played loud with friends; side A sounded especially open.",
                ),
            )

        "release-003" ->
            listOf(
                RecordHistoryEntry(
                    "2026-04-21",
                    "A",
                    5,
                    "Calm",
                    true,
                    "Quiet pressing, perfect for a slower evening.",
                ),
                RecordHistoryEntry("2026-04-12", "B", 4, "Nostalgic", false, null),
                RecordHistoryEntry(
                    "2026-03-30",
                    "A",
                    5,
                    "Relaxed",
                    true,
                    "The vocal detail stood out more than last time.",
                ),
            )

        else ->
            listOf(
                RecordHistoryEntry(
                    "2026-04-25",
                    "A",
                    5,
                    "Calm",
                    true,
                    "Great clarity after cleaning; bass stayed tight.",
                ),
                RecordHistoryEntry("2026-04-20", "B", 5, "Focused", false, null),
                RecordHistoryEntry(
                    "2026-04-15",
                    "A",
                    4,
                    "Nostalgic",
                    true,
                    "Slight surface noise near the end, but still a lovely play.",
                ),
            )
    }
}

internal fun hasRecordDetailSessionData(
    releaseId: String,
    sessions: List<ListeningSession>,
): Boolean = sessions.isNotEmpty() || shouldUsePrototypeRecordDetailFallback(releaseId)

internal fun shouldShowCollectionRemovedMessage(record: RecordSummary): Boolean =
    !record.inCollection && !record.collectionRemovedAt.isNullOrBlank()

internal fun shouldShowGetFullReleaseAction(record: RecordSummary): Boolean =
    record.inCollection && !record.hasFullDiscogsInfo && !shouldUsePrototypeRecordDetailFallback(record.releaseId)

internal fun recordCollectionRemovedMessage(record: RecordSummary): String = "This record was removed from your Discogs collection."

private fun shouldUsePrototypeRecordDetailFallback(releaseId: String): Boolean =
    releaseId in setOf("release-001", "release-002", "release-003")
