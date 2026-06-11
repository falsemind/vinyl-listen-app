package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.FabPosition
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.HomeSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.TopRecordSummary
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.EditableSessionButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionActionHeader
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun HomeScreen(
    apiClient: VinylApiClient,
    onLogSession: () -> Unit,
    onOpenRecord: (String) -> Unit,
    onOpenAnalytics: () -> Unit,
    onOpenInsights: () -> Unit,
    onOpenCollection: () -> Unit,
    onOpenSettings: () -> Unit,
    onViewAllSessions: () -> Unit,
    onEditSession: (String) -> Unit,
    hasActiveTimedSession: Boolean = false,
    isStartingTimedSession: Boolean = false,
    onStartTimedSession: () -> Unit = {},
) {
    var homeSummary by remember { mutableStateOf(mockHomeSummary()) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getHomeSummary(recentLimit = 5, topLimit = 25) }
            .onSuccess {
                homeSummary = it
                loadError = null
            }.onFailure { error ->
                loadError = error.toUserMessage("Could not load latest sessions. Showing local prototype data.")
            }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = true, onClick = {}),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onOpenAnalytics),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onOpenInsights),
                        BottomNavItem(
                            "Collection",
                            Icons.Filled.LibraryMusic,
                            selected = false,
                            onClick = onOpenCollection,
                        ),
                    ),
            )
        },
        floatingActionButton = {
            FloatingGlassButton(
                label = "Log Session",
                onClick = onLogSession,
                modifier =
                    Modifier.padding(
                        end = VinylSpacing.SpaceMd,
                        bottom = VinylSpacing.SpaceLg,
                    ),
            )
        },
        floatingActionButtonPosition = FabPosition.End,
    ) { innerPadding ->
        ScreenContent(
            title = "Vinyl Listen",
            subtitle = "Your collection is ready for the next spin.",
            innerPadding = innerPadding,
            titleEndContent = {
                IconButton(onClick = onOpenSettings) {
                    Icon(
                        imageVector = Icons.Filled.Settings,
                        contentDescription = "Open settings",
                        tint = VinylColors.TextSecondary,
                    )
                }
            },
            topStartContent = {
                if (!hasActiveTimedSession) {
                    StartTimedSessionAction(
                        isStarting = isStartingTimedSession,
                        onClick = onStartTimedSession,
                    )
                }
            },
        ) {
            loadError?.let { message ->
                ErrorRetryCard(message = message, onRetry = { retryKey += 1 })
            }
            SectionActionHeader("Recent Sessions", action = "View All", onActionClick = onViewAllSessions)
            if (homeSummary.recentSessions.isEmpty()) {
                EmptyHomeState("No sessions logged yet.")
            } else {
                homeSummary.recentSessions.take(3).forEach { session ->
                    SessionRow(
                        session = session,
                        onClick = { onOpenRecord(session.releaseId) },
                        onEditSession = { sessionId -> onEditSession(sessionId) },
                    )
                }
            }

            SectionTitle("Collection Snapshot")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                SnapshotCard(
                    label = "Total Sessions",
                    value = homeSummary.totalSessions.toString(),
                    modifier = Modifier.weight(1f),
                    accentColor = VinylColors.AccentGreen,
                )
                SnapshotCard(
                    label = "Records This Month",
                    value = homeSummary.recordsThisMonth.toString(),
                    modifier = Modifier.weight(1f),
                    accentColor = VinylColors.AccentOrange,
                )
            }

            SectionTitle("Top Records")
            homeTopRecordHighlights(homeSummary.topRecords).forEachIndexed { index, topRecord ->
                TopRecordRow(
                    topRecord = topRecord,
                    badge = if (index == 0) "Most Played" else "Least Played",
                    badgeColor = if (index == 0) VinylColors.AccentGreen else VinylColors.AccentOrange,
                    onClick = { onOpenRecord(topRecord.record.releaseId) },
                )
            }
        }
    }
}

@Composable
private fun StartTimedSessionAction(
    isStarting: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(72.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.AccentGreen.copy(alpha = 0.14f))
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.62f), VinylShapes.Card)
                .clickable(
                    enabled = !isStarting,
                    onClickLabel = "Start timed session",
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceLg),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = if (isStarting) "Starting Timed Session..." else "Start Timed Session",
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.weight(1f),
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TimedSessionActionIcon(
                icon = Icons.Filled.Add,
                contentDescription = "Add records to timed session",
                selected = false,
            )
            TimedSessionActionIcon(
                icon = if (isStarting) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                contentDescription = if (isStarting) "Starting timed session" else "Start timed session",
                selected = true,
            )
        }
    }
}

@Composable
private fun TimedSessionActionIcon(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    contentDescription: String,
    selected: Boolean,
) {
    Box(
        modifier =
            Modifier
                .size(42.dp)
                .clip(CircleShape)
                .background(if (selected) VinylColors.AccentGreen else androidx.compose.ui.graphics.Color.Transparent)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.7f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = if (selected) VinylColors.TextOnAccent else VinylColors.AccentGreen,
            modifier = Modifier.size(22.dp),
        )
    }
}

private const val COMPACT_HOME_BREAKPOINT_DP = 430

private val VinylColorsChipShape = VinylShapes.Chip

private fun mockHomeSummary(): HomeSummary =
    HomeSummary(
        recentSessions = MockVinylData.recentSessions,
        totalSessions = 128,
        recordsThisMonth = 24,
        topRecords = MockVinylData.topRecords,
    )

private fun homeTopRecordHighlights(records: List<TopRecordSummary>): List<TopRecordSummary> {
    val mostPlayed = records.maxByOrNull { it.plays }
    val leastPlayed = records.minByOrNull { it.plays }
    return listOfNotNull(mostPlayed, leastPlayed.takeIf { it?.record?.releaseId != mostPlayed?.record?.releaseId })
}

@Composable
private fun SnapshotCard(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    accentColor: androidx.compose.ui.graphics.Color = VinylColors.AccentGreen,
) {
    AccentCard(
        modifier = modifier.height(128.dp),
        borderColor = accentColor.copy(alpha = 0.35f),
    ) {
        CardTopAccentLine(accentColor = accentColor, alpha = 0.45f)
        Text(
            text = value,
            color = accentColor,
            fontSize = 40.sp,
            lineHeight = 44.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(label, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun EmptyHomeState(message: String) {
    AccentCard(borderColor = VinylColors.BorderDefault) {
        Text(
            text = message,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun RecordRow(
    record: RecordSummary,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Text(record.title, color = VinylColors.TextPrimary, style = MaterialTheme.typography.titleMedium)
        Text(record.artist, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "${record.label} - ${record.year}",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            RatingStars(record.rating)
        }
    }
}

@Composable
private fun TopRecordRow(
    topRecord: TopRecordSummary,
    badge: String,
    badgeColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
) {
    val compact = LocalConfiguration.current.screenWidthDp < COMPACT_HOME_BREAKPOINT_DP
    val record = topRecord.record

    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
        borderColor = badgeColor.copy(alpha = 0.35f),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = if (compact) VinylSpacing.SpaceXs else VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = badgeColor,
                compact = compact,
                imageUrl = record.coverImageUrl,
                contentDescription = "${record.title} cover art",
            )
            Spacer(Modifier.width(if (compact) VinylSpacing.SpaceMd else VinylSpacing.SpaceLg))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = record.title,
                    color = VinylColors.TextPrimary,
                    style = if (compact) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.titleMedium,
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
                Row(
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = "${topRecord.plays} plays",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        text = if (compact) "Avg ${topRecord.averageRating}" else "Avg Rating: ${topRecord.averageRating}",
                        color = VinylColors.TextPrimary,
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.End,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                }
                if (compact) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End,
                    ) {
                        TopRecordBadge(badge = badge, badgeColor = badgeColor, compact = true)
                    }
                }
            }
            if (!compact) {
                TopRecordBadge(badge = badge, badgeColor = badgeColor, compact = false)
            }
        }
    }
}

@Composable
private fun TopRecordBadge(
    badge: String,
    badgeColor: androidx.compose.ui.graphics.Color,
    compact: Boolean,
) {
    Text(
        modifier =
            Modifier
                .padding(start = if (compact) 0.dp else VinylSpacing.SpaceMd)
                .background(badgeColor.copy(alpha = 0.16f), VinylColorsChipShape)
                .border(1.dp, badgeColor.copy(alpha = 0.35f), VinylColorsChipShape)
                .padding(
                    horizontal = if (compact) VinylSpacing.SpaceSm else VinylSpacing.SpaceMd,
                    vertical = if (compact) VinylSpacing.SpaceXs else VinylSpacing.SpaceSm,
                ),
        text = badge,
        color = badgeColor,
        style = MaterialTheme.typography.bodyMedium,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun SessionRow(
    session: ListeningSession,
    onClick: () -> Unit,
    onEditSession: (String) -> Unit,
) {
    val compact = LocalConfiguration.current.screenWidthDp < COMPACT_HOME_BREAKPOINT_DP
    val editableSessionId = session.sessionId?.takeIf { session.canEdit && it.isNotBlank() }

    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
        borderColor = VinylColors.BorderDefault,
    ) {
        Box(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = if (compact) VinylSpacing.SpaceXs else VinylSpacing.SpaceSm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AlbumArtBlock(
                    accentColor = VinylColors.AccentGreen,
                    compact = compact,
                    imageUrl = session.thumbnailUrl,
                    contentDescription = "${session.title} cover art",
                )
                Spacer(Modifier.width(if (compact) VinylSpacing.SpaceMd else VinylSpacing.SpaceLg))
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
                ) {
                    Text(
                        modifier = Modifier.padding(end = if (editableSessionId != null) 40.dp else 0.dp),
                        text = session.title,
                        color = VinylColors.TextPrimary,
                        style = if (compact) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.titleMedium,
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
                        horizontalArrangement = Arrangement.spacedBy(if (compact) VinylSpacing.SpaceXs else VinylSpacing.SpaceSm),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        SidePlayedChip(side = session.side, compact = compact)
                        RatingStars(
                            rating = session.rating,
                            compact = compact,
                            starSize = if (compact) 14.dp else 18.dp,
                            strokeWidth = if (compact) 1.5.dp else 2.dp,
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
                    onClick = { onEditSession(id) },
                    modifier = Modifier.align(Alignment.TopEnd),
                )
            }
        }
    }
}

@Composable
private fun SidePlayedChip(
    side: String?,
    compact: Boolean,
) {
    Text(
        modifier =
            Modifier
                .background(VinylColors.AccentGreen, VinylColorsChipShape)
                .padding(
                    horizontal = if (compact) VinylSpacing.SpaceSm else VinylSpacing.SpaceMd,
                    vertical = if (compact) 2.dp else VinylSpacing.SpaceXs,
                ),
        text = side?.let { "Side $it" } ?: "Side -",
        color = VinylColors.TextOnSolidAccent,
        style =
            if (compact) {
                MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp)
            } else {
                MaterialTheme.typography.bodyMedium
            },
    )
}
