package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.FabPosition
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
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
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.ScreenContent
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
    onOpenSettings: () -> Unit,
    onViewAllSessions: () -> Unit,
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
                        BottomNavItem("Settings", Icons.Filled.Settings, selected = false, onClick = onOpenSettings),
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
        ) {
            SectionHeader("Recent Sessions", action = "View All", onActionClick = onViewAllSessions)
            loadError?.let { message ->
                HomeRecoveryCard(message = message, onRetry = { retryKey += 1 })
            }
            if (homeSummary.recentSessions.isEmpty()) {
                EmptyHomeState("No sessions logged yet.")
            } else {
                homeSummary.recentSessions.take(3).forEach { session ->
                    SessionRow(session, onClick = { onOpenRecord(session.releaseId) })
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

private const val COMPACT_HOME_BREAKPOINT_DP = 430

private val VinylColorsChipShape = VinylShapes.Chip

private fun mockHomeSummary(): HomeSummary =
    HomeSummary(
        recentSessions = MockVinylData.recentSessions,
        totalSessions = 128,
        recordsThisMonth = 24,
        topRecords = MockVinylData.topRecords,
    )

@Composable
private fun SectionHeader(
    label: String,
    action: String,
    onActionClick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SectionTitle(label)
        Text(
            modifier =
                Modifier.clickable(
                    onClickLabel = action,
                    role = androidx.compose.ui.semantics.Role.Button,
                    onClick = onActionClick,
                ),
            text = action,
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

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
private fun HomeRecoveryCard(
    message: String,
    onRetry: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClick = onRetry),
        borderColor = VinylColors.AccentOrange.copy(alpha = 0.35f),
    ) {
        Text(
            text = "$message Tap to retry.",
            color = VinylColors.AccentOrange,
            style = MaterialTheme.typography.bodyMedium,
        )
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
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = "${topRecord.plays} plays",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = if (compact) "Avg ${topRecord.averageRating}" else "Avg Rating: ${topRecord.averageRating}",
                        color = VinylColors.TextPrimary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
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
) {
    val compact = LocalConfiguration.current.screenWidthDp < COMPACT_HOME_BREAKPOINT_DP

    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
        borderColor = VinylColors.BorderDefault,
    ) {
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
                    text = session.title,
                    color = VinylColors.TextPrimary,
                    style = if (compact) MaterialTheme.typography.bodyLarge else MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
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
                }
            }
            Text(
                modifier = Modifier.padding(start = VinylSpacing.SpaceSm),
                text = relativeLastPlayedLabel(session.playedAt),
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
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
