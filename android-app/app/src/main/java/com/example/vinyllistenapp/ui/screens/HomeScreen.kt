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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowUp
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
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
import com.example.vinyllistenapp.ui.components.timedSessionMoodDirectionLabel
import com.example.vinyllistenapp.ui.components.timedSessionStyleFocusLabel
import com.example.vinyllistenapp.ui.components.timedSessionTypeLabel
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
    autoAddTimedSessionRecords: Boolean = true,
    onAutoAddTimedSessionRecordsToggle: () -> Unit = {},
    onStartTimedSession: (styleFocus: String, moodDirection: String, sessionType: String) -> Unit = { _, _, _ -> },
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
                        autoAddEnabled = autoAddTimedSessionRecords,
                        onAutoAddToggle = onAutoAddTimedSessionRecordsToggle,
                        onStart = onStartTimedSession,
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
    autoAddEnabled: Boolean,
    onAutoAddToggle: () -> Unit,
    onStart: (styleFocus: String, moodDirection: String, sessionType: String) -> Unit,
) {
    var isExpanded by remember { mutableStateOf(false) }
    var selectedSessionType by remember { mutableStateOf(TIMED_SESSION_TYPE_OPTIONS.first()) }
    var selectedStyleFocus by remember { mutableStateOf(TIMED_SESSION_STYLE_OPTIONS.first()) }
    var selectedMoodDirection by remember { mutableStateOf(TIMED_SESSION_MOOD_OPTIONS.first()) }
    val arrowRotation by animateFloatAsState(
        targetValue = if (isExpanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "startTimedSessionArrow",
    )

    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.AccentGreen.copy(alpha = 0.14f))
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.62f), VinylShapes.Card),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(72.dp)
                    .clickable(
                        enabled = !isStarting,
                        onClickLabel = if (isExpanded) "Collapse timed session setup" else "Expand timed session setup",
                        role = Role.Button,
                        onClick = { isExpanded = !isExpanded },
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
        if (isExpanded) {
            HomeTimedSessionDivider()
            Column(
                modifier =
                    Modifier.padding(
                        start = VinylSpacing.SpaceLg,
                        top = VinylSpacing.SpaceMd,
                        end = VinylSpacing.SpaceLg,
                        bottom = VinylSpacing.SpaceMd,
                    ),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            ) {
                TimedSessionSetupRow(
                    label = "Session type",
                    selectedOption = selectedSessionType,
                    options = TIMED_SESSION_TYPE_OPTIONS,
                    enabled = !isStarting,
                    onOptionSelected = { selectedSessionType = it },
                )
                TimedSessionSetupRow(
                    label = "Style",
                    selectedOption = selectedStyleFocus,
                    options = TIMED_SESSION_STYLE_OPTIONS,
                    enabled = !isStarting,
                    onOptionSelected = { selectedStyleFocus = it },
                )
                TimedSessionSetupRow(
                    label = "Mood direction",
                    selectedOption = selectedMoodDirection,
                    options = TIMED_SESSION_MOOD_OPTIONS,
                    enabled = !isStarting,
                    onOptionSelected = { selectedMoodDirection = it },
                )
            }
            HomeTimedSessionDivider()
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = VinylSpacing.SpaceLg, vertical = VinylSpacing.SpaceMd),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TimedSessionSetupAction(
                    icon = if (autoAddEnabled) Icons.Filled.Check else Icons.Filled.Add,
                    label = "Auto add records",
                    selected = autoAddEnabled,
                    enabled = !isStarting,
                    onClick = onAutoAddToggle,
                    modifier = Modifier.weight(1f),
                )
                TimedSessionSetupAction(
                    icon = if (isStarting) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                    label = "Start session",
                    selected = true,
                    enabled = !isStarting,
                    onClick = {
                        onStart(
                            selectedStyleFocus.apiValue,
                            selectedMoodDirection.apiValue,
                            selectedSessionType.apiValue,
                        )
                    },
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun TimedSessionSetupRow(
    label: String,
    selectedOption: TimedSessionSetupOption,
    options: List<TimedSessionSetupOption>,
    enabled: Boolean,
    onOptionSelected: (TimedSessionSetupOption) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
        TimedSessionSetupSelector(
            selectedOption = selectedOption,
            options = options,
            enabled = enabled,
            onOptionSelected = onOptionSelected,
        )
    }
}

@Composable
private fun TimedSessionSetupSelector(
    selectedOption: TimedSessionSetupOption,
    options: List<TimedSessionSetupOption>,
    enabled: Boolean,
    onOptionSelected: (TimedSessionSetupOption) -> Unit,
) {
    var isMenuOpen by remember { mutableStateOf(false) }
    var selectorWidth by remember { mutableStateOf(Dp.Unspecified) }
    val density = LocalDensity.current
    val arrowRotation by animateFloatAsState(
        targetValue = if (isMenuOpen) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "timedSessionSetupSelectorArrow",
    )
    val selectorControlWidth = 164.dp
    val selectorControlHeight = 42.dp

    Box(
        modifier =
            Modifier
                .width(selectorControlWidth)
                .onGloballyPositioned { coordinates ->
                    selectorWidth = with(density) { coordinates.size.width.toDp() }
                },
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.72f), VinylShapes.Card)
                    .clickable(
                        enabled = enabled,
                        onClickLabel = "Open ${selectedOption.label} selector",
                        role = Role.Button,
                        onClick = { isMenuOpen = !isMenuOpen },
                    ).padding(horizontal = VinylSpacing.SpaceSm)
                    .height(selectorControlHeight),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = selectedOption.label,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(
                imageVector = Icons.Filled.KeyboardArrowUp,
                contentDescription = null,
                tint = VinylColors.AccentGreen,
                modifier =
                    Modifier
                        .size(24.dp)
                        .graphicsLayer { rotationZ = arrowRotation },
            )
        }
        if (isMenuOpen) {
            Popup(
                alignment = Alignment.TopStart,
                offset = IntOffset(x = 0, y = with(density) { 48.dp.roundToPx() }),
                onDismissRequest = { isMenuOpen = false },
                properties = PopupProperties(focusable = true),
            ) {
                Column(
                    modifier =
                        Modifier
                            .width(selectorWidth.takeIf { it != Dp.Unspecified } ?: selectorControlWidth)
                            .shadow(4.dp, VinylShapes.Card)
                            .clip(VinylShapes.Card)
                            .background(VinylColors.SurfacePrimary)
                            .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.72f), VinylShapes.Card)
                            .verticalScroll(rememberScrollState()),
                ) {
                    options.forEachIndexed { index, option ->
                        TimedSessionSetupOptionRow(
                            option = option,
                            selected = option == selectedOption,
                            alternate = index % 2 == 0,
                            enabled = enabled,
                            onClick = {
                                isMenuOpen = false
                                onOptionSelected(option)
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TimedSessionSetupOptionRow(
    option: TimedSessionSetupOption,
    selected: Boolean,
    alternate: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val rowColor = if (alternate) VinylColors.SurfacePrimary else VinylColors.SurfaceSecondary
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(rowColor)
                .clickable(
                    enabled = enabled,
                    role = Role.RadioButton,
                    onClickLabel = "Select ${option.label}",
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceSm, vertical = VinylSpacing.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Box(
            modifier =
                Modifier
                    .size(20.dp)
                    .clip(CircleShape)
                    .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                    .border(
                        width = 1.dp,
                        color = if (selected) VinylColors.AccentGreen else VinylColors.BorderDefault,
                        shape = CircleShape,
                    ),
            contentAlignment = Alignment.Center,
        ) {
            if (selected) {
                Icon(
                    imageVector = Icons.Filled.Check,
                    contentDescription = null,
                    tint = VinylColors.SurfacePrimary,
                    modifier = Modifier.size(14.dp),
                )
            }
        }
        Text(
            text = option.label,
            color = if (selected) VinylColors.AccentGreen else VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun TimedSessionSetupAction(
    icon: ImageVector,
    label: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
    ) {
        Box(
            modifier =
                Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.7f), CircleShape)
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
                modifier = Modifier.size(22.dp),
            )
        }
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun HomeTimedSessionDivider() {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(VinylColors.AccentGreen.copy(alpha = 0.34f)),
    )
}

private data class TimedSessionSetupOption(
    val apiValue: String,
    val label: String,
)

private val TIMED_SESSION_TYPE_OPTIONS =
    listOf(
        TimedSessionSetupOption("casual_listening", timedSessionTypeLabel("casual_listening")),
        TimedSessionSetupOption("dj_set", timedSessionTypeLabel("dj_set")),
        TimedSessionSetupOption("rediscovery", timedSessionTypeLabel("rediscovery")),
        TimedSessionSetupOption("testing_records", timedSessionTypeLabel("testing_records")),
        TimedSessionSetupOption("background", timedSessionTypeLabel("background")),
    )

private val TIMED_SESSION_STYLE_OPTIONS =
    listOf(
        TimedSessionSetupOption("mixed", timedSessionStyleFocusLabel("mixed")),
        TimedSessionSetupOption("one_style", timedSessionStyleFocusLabel("one_style")),
        TimedSessionSetupOption("random", timedSessionStyleFocusLabel("random")),
    )

private val TIMED_SESSION_MOOD_OPTIONS =
    listOf(
        TimedSessionSetupOption("steady_mood", timedSessionMoodDirectionLabel("steady_mood")),
        TimedSessionSetupOption("mood_switch", timedSessionMoodDirectionLabel("mood_switch")),
        TimedSessionSetupOption("energy_build", timedSessionMoodDirectionLabel("energy_build")),
        TimedSessionSetupOption("cool_down", timedSessionMoodDirectionLabel("cool_down")),
    )

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
