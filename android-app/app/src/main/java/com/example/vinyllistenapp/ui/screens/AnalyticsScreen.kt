package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.AnalyticsDashboard
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.MonthlyPlayCount
import com.example.vinyllistenapp.domain.MoodDistributionItem
import com.example.vinyllistenapp.domain.RatingDistributionItem
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun AnalyticsScreen(
    apiClient: VinylApiClient,
    onHome: () -> Unit,
    onOpenRecord: (String) -> Unit,
    onSettings: () -> Unit,
) {
    var dashboard by remember { mutableStateOf(mockAnalyticsDashboard()) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(retryKey) {
        runCatching { apiClient.getAnalyticsDashboard() }
            .onSuccess {
                dashboard = it
                loadError = null
            }.onFailure { error ->
                loadError = error.toUserMessage("Could not load analytics. Showing local prototype data.")
            }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", selected = false, onClick = onHome),
                        BottomNavItem("Stats", selected = true, onClick = {}),
                        BottomNavItem("Settings", selected = false, onClick = onSettings),
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
                AnalyticsRecoveryCard(message = message, onRetry = { retryKey += 1 })
            }
            SectionTitle("Plays Over Time")
            MonthlyPlaysCard(monthlyPlays = dashboard.monthlyPlays)
            SectionTitle("Top Records")
            dashboard.topRecords.forEachIndexed { index, record ->
                TopRecordAnalyticsCard(
                    record = record,
                    accentColor = analyticsAccent(index),
                    maxPlays = dashboard.topRecords.maxOfOrNull { it.plays } ?: 1,
                    onClick = { onOpenRecord(record.record.releaseId) },
                )
            }
            SectionTitle("Rating Distribution")
            RatingDistributionCard(ratings = dashboard.ratingDistribution)
            SectionTitle("Mood Distribution")
            MoodDistributionCard(moods = dashboard.moodDistribution)
        }
    }
}

@Composable
private fun MonthlyPlaysCard(monthlyPlays: List<MonthlyPlayCount>) {
    val totalSessions = monthlyPlays.sumOf { it.plays }
    val maxPlays = monthlyPlays.maxOfOrNull { it.plays }?.takeIf { it > 0 } ?: 1

    AccentCard {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(132.dp),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.Bottom,
        ) {
            monthlyPlays.forEach { item ->
                MonthlyPlayBar(
                    item = item,
                    maxPlays = maxPlays,
                    modifier = Modifier.weight(1f),
                )
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
                        color = VinylColors.TextOnSolidAccent,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.align(Alignment.CenterEnd).padding(horizontal = VinylSpacing.SpaceSm),
                    )
                }
            }
        }
    }
}

@Composable
private fun MoodDistributionCard(moods: List<MoodDistributionItem>) {
    val total = moods.sumOf { it.count }.coerceAtLeast(1)
    val maxCount = moods.maxOfOrNull { it.count }?.takeIf { it > 0 } ?: 1

    AccentCard {
        moods.forEachIndexed { index, item ->
            val accentColor = analyticsAccent(index)
            val percent = ((item.count.toFloat() / total.toFloat()) * 100).toInt()
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(item.mood, color = VinylColors.TextPrimary, style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
                        Text(item.count.toString(), color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodySmall)
                        Text("$percent%", color = accentColor, style = MaterialTheme.typography.bodySmall)
                    }
                }
                ProgressTrack(
                    fraction = (item.count.toFloat() / maxCount.toFloat()).coerceIn(0f, 1f),
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

@Composable
private fun AnalyticsRecoveryCard(
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

private fun mockAnalyticsDashboard(): AnalyticsDashboard =
    AnalyticsDashboard(
        monthlyPlays =
            listOf(
                MonthlyPlayCount("2026-01", 8),
                MonthlyPlayCount("2026-02", 12),
                MonthlyPlayCount("2026-03", 15),
                MonthlyPlayCount("2026-04", 24),
                MonthlyPlayCount("2026-05", 18),
            ),
        topRecords =
            listOf(
                AnalyticsTopRecordSummary(mockRecord("release-101", "Kind of Blue"), 12, "4.8"),
                AnalyticsTopRecordSummary(mockRecord("release-102", "Blue Train"), 10, "4.5"),
                AnalyticsTopRecordSummary(mockRecord("release-103", "Rumours"), 8, "4.2"),
                AnalyticsTopRecordSummary(mockRecord("release-104", "The Dark Side"), 6, "4.0"),
            ),
        ratingDistribution =
            listOf(
                RatingDistributionItem(5, 28),
                RatingDistributionItem(4, 18),
                RatingDistributionItem(3, 8),
                RatingDistributionItem(2, 3),
                RatingDistributionItem(1, 1),
            ),
        moodDistribution =
            listOf(
                MoodDistributionItem("Calm", 25),
                MoodDistributionItem("Energetic", 18),
                MoodDistributionItem("Focused", 15),
                MoodDistributionItem("Melancholic", 10),
                MoodDistributionItem("Nostalgic", 4),
            ),
    )

private fun mockRecord(
    releaseId: String,
    title: String,
): RecordSummary {
    val fallback = MockVinylData.records.first()
    return fallback.copy(
        releaseId = releaseId,
        title = title,
        artist =
            when (title) {
                "Kind of Blue" -> "Miles Davis"
                "Blue Train" -> "John Coltrane"
                "Rumours" -> "Fleetwood Mac"
                else -> "Pink Floyd"
            },
        lastPlayed = "",
    )
}
