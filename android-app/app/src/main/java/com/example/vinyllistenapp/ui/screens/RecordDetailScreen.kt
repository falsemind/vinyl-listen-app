package com.example.vinyllistenapp.ui.screens

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.RecordDetailAlbumArtBlock
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun RecordDetailScreen(
    releaseId: String?,
    onAddSession: (String) -> Unit,
    onHome: () -> Unit,
) {
    val record = MockVinylData.record(releaseId)

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Text(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = VinylSpacing.SpaceXl)
                        .padding(top = 48.dp, bottom = 40.dp),
                text = "Record Details",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineLarge,
            )
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = VinylSpacing.SpaceXl),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXl),
            ) {
                RecordDetailHeroCard(record = record)
                SectionTitle("Listening Stats")
                RecordDetailStatsRow(record = record)
                SectionTitle("Mood Summary")
                RecordMoodSummaryCard(moodData = recordDetailMoodData(record.releaseId))
                SectionTitle("Recent Sessions")
                Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                    recordDetailHistory(record.releaseId).forEach { history ->
                        RecordHistoryCard(history = history)
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
        RecordDetailBackBar(
            onClick = onHome,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun RecordDetailHeroCard(record: RecordSummary) {
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
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RecordDetailAlbumArtBlock()
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
                        text = "${record.year} - ${record.label}",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = "Cat# ${matchCatalogNumber(record.releaseId, 0)}",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            RecordDiscogsButton()
        }
    }
}

@Composable
private fun RecordDiscogsButton() {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clip(VinylShapes.Button)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                .clickable(onClick = {}),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "View on Discogs",
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun RecordDetailStatsRow(record: RecordSummary) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        RecordStatCard(
            value = recordDetailTotalPlays(record.releaseId).toString(),
            label = "Total Plays",
            accentColor = VinylColors.AccentGreen,
            modifier = Modifier.weight(1f),
        )
        RecordStatCard(
            value = recordDetailAverageRating(record.releaseId),
            label = "Avg Rating",
            accentColor = VinylColors.AccentOrange,
            modifier = Modifier.weight(1f),
        )
        RecordStatCard(
            value = recordDetailLastPlayed(record.releaseId),
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
private fun RecordHistoryCard(history: RecordHistoryEntry) {
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = history.date,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (history.hasNotes) {
                    Text(
                        modifier =
                            Modifier
                                .clip(VinylShapes.Chip)
                                .background(VinylColors.SurfaceSecondary)
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
    }
}

@Composable
private fun RecordDetailBackBar(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .fillMaxWidth()
                .height(80.dp)
                .background(VinylColors.SurfaceSecondary)
                .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier =
                Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(VinylColors.BorderDefault),
        )
        Text(
            text = "Back to Home",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

private data class RecordMoodSummary(
    val mood: String,
    val count: Int,
    val color: androidx.compose.ui.graphics.Color,
)

private data class RecordHistoryEntry(
    val date: String,
    val side: String,
    val rating: Int,
    val mood: String,
    val hasNotes: Boolean,
)

private fun recordDetailTotalPlays(releaseId: String): Int =
    when (releaseId) {
        "release-001" -> 12
        "release-002" -> 8
        "release-003" -> 10
        else -> 6
    }

private fun recordDetailAverageRating(releaseId: String): String =
    when (releaseId) {
        "release-001" -> "4.8"
        "release-002" -> "4.2"
        "release-003" -> "4.7"
        else -> "4.0"
    }

private fun recordDetailLastPlayed(releaseId: String): String =
    when (releaseId) {
        "release-001" -> "5d ago"
        "release-002" -> "1w ago"
        "release-003" -> "2w ago"
        else -> "Recent"
    }

private fun recordDetailMoodData(releaseId: String): List<RecordMoodSummary> =
    when (releaseId) {
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

private fun recordDetailHistory(releaseId: String): List<RecordHistoryEntry> =
    when (releaseId) {
        "release-002" ->
            listOf(
                RecordHistoryEntry("Apr 25, 2026", "A", 4, "Late night", true),
                RecordHistoryEntry("Apr 18, 2026", "B", 4, "Focused", false),
                RecordHistoryEntry("Apr 03, 2026", "A", 5, "Social", true),
            )

        "release-003" ->
            listOf(
                RecordHistoryEntry("Apr 21, 2026", "A", 5, "Calm", true),
                RecordHistoryEntry("Apr 12, 2026", "B", 4, "Nostalgic", false),
                RecordHistoryEntry("Mar 30, 2026", "A", 5, "Relaxed", true),
            )

        else ->
            listOf(
                RecordHistoryEntry("Apr 25, 2026", "A", 5, "Calm", true),
                RecordHistoryEntry("Apr 20, 2026", "B", 5, "Focused", false),
                RecordHistoryEntry("Apr 15, 2026", "A", 4, "Nostalgic", true),
            )
    }
