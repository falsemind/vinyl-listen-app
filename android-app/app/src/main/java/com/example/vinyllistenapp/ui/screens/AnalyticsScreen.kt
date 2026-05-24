package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsDashboard
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.MonthlyPlayCount
import com.example.vinyllistenapp.domain.MoodDistributionItem
import com.example.vinyllistenapp.domain.RatingDistributionItem
import com.example.vinyllistenapp.domain.StyleDistributionItem
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionActionHeader
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun AnalyticsScreen(
    apiClient: VinylApiClient,
    onHome: () -> Unit,
    onOpenRecord: (String) -> Unit,
    onInsights: () -> Unit,
    onSettings: () -> Unit,
    onViewAllTopRecords: () -> Unit,
    onViewAllMoods: () -> Unit,
    onViewAllStyles: () -> Unit,
) {
    var dashboard by remember { mutableStateOf(emptyAnalyticsDashboard()) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getAnalyticsDashboard() }
            .onSuccess {
                dashboard = it
                loadError = null
            }.onFailure { error ->
                loadError = error.toUserMessage("Could not load analytics.")
            }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = true, onClick = {}),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onInsights),
                        BottomNavItem("Settings", Icons.Filled.Settings, selected = false, onClick = onSettings),
                    ),
            )
        },
    ) { innerPadding ->
        ScreenContent(
            title = "Analytics",
            subtitle = "Your listening insights",
            innerPadding = innerPadding,
        ) {
            loadError?.let { message ->
                ErrorRetryCard(message = message, onRetry = { retryKey += 1 })
            }
            SectionTitle("Plays Over Time")
            MonthlyPlaysCard(monthlyPlays = dashboard.monthlyPlays)
            if (dashboard.topRecords.isEmpty()) {
                SectionTitle("Top Records")
                AnalyticsEmptySectionText()
            } else {
                SectionActionHeader("Top Records", action = "View All", onActionClick = onViewAllTopRecords)
                dashboard.topRecords.take(5).forEachIndexed { index, record ->
                    TopRecordAnalyticsCard(
                        record = record,
                        accentColor = analyticsAccent(index),
                        maxPlays = dashboard.topRecords.maxOfOrNull { it.plays } ?: 1,
                        onClick = { onOpenRecord(record.record.releaseId) },
                    )
                }
            }
            SectionTitle("Rating Distribution")
            if (dashboard.ratingDistribution.isEmpty()) {
                AnalyticsEmptySectionText()
            } else {
                RatingDistributionCard(ratings = dashboard.ratingDistribution)
            }
            if (dashboard.moodDistribution.size > MOOD_DISTRIBUTION_PREVIEW_LIMIT) {
                SectionActionHeader("Mood Distribution", action = "View All", onActionClick = onViewAllMoods)
            } else {
                SectionTitle("Mood Distribution")
            }
            if (dashboard.moodDistribution.isEmpty()) {
                AnalyticsEmptySectionText()
            } else {
                MoodDistributionCard(moods = dashboard.moodDistribution.take(MOOD_DISTRIBUTION_PREVIEW_LIMIT))
            }
            if (dashboard.styleDistribution.size > STYLE_DISTRIBUTION_PREVIEW_LIMIT) {
                SectionActionHeader("Style Distribution", action = "View All", onActionClick = onViewAllStyles)
            } else {
                SectionTitle("Style Distribution")
            }
            if (dashboard.styleDistribution.isEmpty()) {
                AnalyticsEmptySectionText()
            } else {
                StyleDistributionCard(styles = dashboard.styleDistribution.take(STYLE_DISTRIBUTION_PREVIEW_LIMIT))
            }
        }
    }
}

private const val MOOD_DISTRIBUTION_PREVIEW_LIMIT = 10
private const val STYLE_DISTRIBUTION_PREVIEW_LIMIT = 10
private const val ANALYTICS_EMPTY_SECTION_TEXT = "No data yet. Start you listening journey!"
private val MONTHLY_PLAY_BAR_WIDTH = 48.dp

@Composable
private fun AnalyticsEmptySectionText() {
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = ANALYTICS_EMPTY_SECTION_TEXT,
        color = VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun MonthlyPlaysCard(monthlyPlays: List<MonthlyPlayCount>) {
    val displayMonths = lastTwelveMonths(monthlyPlays)
    val monthScrollState = rememberScrollState(initial = Int.MAX_VALUE)
    val totalSessions = displayMonths.sumOf { it.plays }
    val maxPlays = displayMonths.maxOfOrNull { it.plays }?.takeIf { it > 0 } ?: 1
    val monthGap = VinylSpacing.SpaceSm
    val minimumChartWidth =
        MONTHLY_PLAY_BAR_WIDTH * displayMonths.size +
            monthGap * (displayMonths.size - 1).coerceAtLeast(0)
    val density = LocalDensity.current
    var availableChartWidthPx by remember { mutableIntStateOf(0) }
    val availableChartWidth = with(density) { availableChartWidthPx.toDp() }
    val shouldFillWidth = availableChartWidthPx > 0 && availableChartWidth >= minimumChartWidth
    val shouldSnapToCurrentMonth = availableChartWidthPx > 0 && !shouldFillWidth

    LaunchedEffect(shouldSnapToCurrentMonth, displayMonths.lastOrNull()?.month) {
        if (shouldSnapToCurrentMonth) {
            val maxScroll =
                monthScrollState.maxValue.takeIf { it > 0 }
                    ?: snapshotFlow { monthScrollState.maxValue }
                        .filter { it > 0 }
                        .first()
            monthScrollState.scrollTo(maxScroll)
        }
    }

    AccentCard {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .onSizeChanged { availableChartWidthPx = it.width },
        ) {
            val rowModifier =
                if (shouldFillWidth) {
                    Modifier.fillMaxWidth()
                } else {
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(monthScrollState)
                }
            Row(
                modifier = rowModifier.height(132.dp),
                horizontalArrangement = Arrangement.spacedBy(monthGap),
                verticalAlignment = Alignment.Bottom,
            ) {
                displayMonths.forEach { item ->
                    MonthlyPlayBar(
                        item = item,
                        maxPlays = maxPlays,
                        modifier =
                            if (shouldFillWidth) {
                                Modifier.weight(1f)
                            } else {
                                Modifier.width(MONTHLY_PLAY_BAR_WIDTH)
                            },
                    )
                }
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
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("Total Sessions", color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
            Text(
                totalSessions.toString(),
                color = VinylColors.AccentGreen,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun MonthlyPlayBar(
    item: MonthlyPlayCount,
    maxPlays: Int,
    modifier: Modifier = Modifier,
) {
    val ratio = (item.plays.toFloat() / maxPlays.toFloat()).coerceIn(0f, 1f)
    val height = (18 + ratio * 86).dp

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Bottom,
    ) {
        Box(
            modifier =
                Modifier
                    .height(104.dp)
                    .fillMaxWidth(),
            contentAlignment = Alignment.BottomCenter,
        ) {
            if (item.plays == 0) {
                Box(
                    modifier =
                        Modifier
                            .width(46.dp)
                            .height(2.dp)
                            .background(VinylColors.TextSecondary.copy(alpha = 0.75f)),
                )
            } else {
                Box(
                    modifier =
                        Modifier
                            .width(46.dp)
                            .height(height)
                            .clip(RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
                            .background(
                                Brush.verticalGradient(
                                    listOf(
                                        VinylColors.AccentGreen,
                                        VinylColors.AccentGreen.copy(alpha = 0.45f),
                                    ),
                                ),
                            ),
                )
            }
        }
        Text(
            text = shortMonthLabel(item.month),
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Clip,
        )
    }
}

@Composable
private fun TopRecordAnalyticsCard(
    record: AnalyticsTopRecordSummary,
    accentColor: Color,
    maxPlays: Int,
    onClick: () -> Unit,
) {
    val fraction = (record.plays.toFloat() / maxPlays.toFloat()).coerceIn(0f, 1f)

    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = record.record.title,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "${record.plays} plays",
                color = accentColor,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.End,
                modifier =
                    Modifier
                        .padding(start = VinylSpacing.SpaceMd)
                        .widthIn(min = 72.dp),
            )
        }
        ProgressTrack(fraction = fraction, accentColor = accentColor)
    }
}

@Composable
private fun RatingDistributionCard(ratings: List<RatingDistributionItem>) {
    val maxCount = ratings.maxOfOrNull { it.count }?.takeIf { it > 0 } ?: 1

    AccentCard {
        ratings.sortedByDescending { it.rating }.forEach { item ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                RatingStars(
                    rating = item.rating,
                    compact = true,
                    modifier = Modifier.width(78.dp),
                )
                Box(
                    modifier =
                        Modifier
                            .weight(1f)
                            .height(24.dp)
                            .clip(VinylShapes.Chip)
                            .background(VinylColors.SurfaceSecondary),
                ) {
                    Box(
                        modifier =
                            Modifier
                                .fillMaxWidth((item.count.toFloat() / maxCount.toFloat()).coerceIn(0f, 1f))
                                .height(24.dp)
                                .clip(VinylShapes.Chip)
                                .background(VinylColors.AccentOrange),
                    )
                    Text(
                        text = item.count.toString(),
                        color =
                            if ((item.count.toFloat() / maxCount.toFloat()).coerceIn(0f, 1f) >= 0.86f) {
                                VinylColors.AppBackground
                            } else {
                                VinylColors.AccentOrange
                            },
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.align(Alignment.CenterEnd).padding(horizontal = VinylSpacing.SpaceSm),
                    )
                }
            }
        }
    }
}

@Composable
internal fun MoodDistributionCard(moods: List<MoodDistributionItem>) {
    DistributionBarCard(
        items = moods,
        label = { it.mood },
        count = { it.count },
    )
}

@Composable
internal fun StyleDistributionCard(styles: List<StyleDistributionItem>) {
    DistributionBarCard(
        items = styles,
        label = { it.style },
        count = { it.count },
    )
}

@Composable
private fun <T> DistributionBarCard(
    items: List<T>,
    label: (T) -> String,
    count: (T) -> Int,
) {
    val total = items.sumOf(count).coerceAtLeast(1)
    val maxCount = items.maxOfOrNull(count)?.takeIf { it > 0 } ?: 1

    AccentCard {
        items.forEachIndexed { index, item ->
            val accentColor = analyticsAccent(index)
            val itemCount = count(item)
            val percent = ((itemCount.toFloat() / total.toFloat()) * 100).toInt()
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(label(item), color = VinylColors.TextPrimary, style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
                        Text(itemCount.toString(), color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodySmall)
                        Text("$percent%", color = accentColor, style = MaterialTheme.typography.bodySmall)
                    }
                }
                ProgressTrack(
                    fraction = (itemCount.toFloat() / maxCount.toFloat()).coerceIn(0f, 1f),
                    accentColor = accentColor,
                )
            }
        }
    }
}

@Composable
private fun ProgressTrack(
    fraction: Float,
    accentColor: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(VinylShapes.Chip)
                .background(VinylColors.SurfaceSecondary),
    ) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth(fraction.coerceIn(0f, 1f))
                    .height(8.dp)
                    .clip(VinylShapes.Chip)
                    .background(accentColor),
        )
    }
}

private fun analyticsAccent(index: Int): Color =
    when (index % 3) {
        0 -> VinylColors.AccentGreen
        1 -> VinylColors.AccentOrange
        else -> VinylColors.AccentPurple
    }

private fun shortMonthLabel(month: String): String =
    runCatching {
        YearMonth.parse(month).month.getDisplayName(TextStyle.SHORT, Locale.US)
    }.getOrDefault(month.takeLast(3))

internal fun lastTwelveMonths(
    monthlyPlays: List<MonthlyPlayCount>,
    currentMonth: YearMonth = YearMonth.now(),
): List<MonthlyPlayCount> {
    val playsByMonth = monthlyPlays.associateBy { it.month }
    return (11 downTo 0).map { offset ->
        val month = currentMonth.minusMonths(offset.toLong())
        playsByMonth[month.toString()] ?: MonthlyPlayCount(month.toString(), 0)
    }
}

internal fun emptyAnalyticsDashboard(): AnalyticsDashboard =
    AnalyticsDashboard(
        monthlyPlays = emptyList(),
        topRecords = emptyList(),
        ratingDistribution = emptyList(),
        moodDistribution = emptyList(),
        styleDistribution = emptyList(),
    )
