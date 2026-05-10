package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FabPosition
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.ConfidenceChip
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.components.MoodChip
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.SecondaryButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun HomeScreen(
    onLogSession: () -> Unit,
    onOpenRecord: (String) -> Unit,
) {
    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", selected = true, onClick = {}),
                        BottomNavItem("Stats", selected = false, onClick = {}),
                        BottomNavItem("Settings", selected = false, onClick = {}),
                    ),
            )
        },
        floatingActionButton = {
            FloatingGlassButton(
                label = "Log Session",
                onClick = onLogSession,
                modifier =
                    Modifier.padding(
                        end = VinylSpacing.SpaceXl,
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
            SectionHeader("Recent Sessions", action = "View All")
            MockVinylData.recentSessions.forEach { session ->
                SessionRow(session, onClick = { onOpenRecord(session.releaseId) })
            }

            SectionTitle("Collection Snapshot")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                SnapshotCard(
                    label = "Total Sessions",
                    value = "128",
                    modifier = Modifier.weight(1f),
                    accentColor = VinylColors.AccentGreen,
                )
                SnapshotCard(
                    label = "Records This Month",
                    value = "24",
                    modifier = Modifier.weight(1f),
                    accentColor = VinylColors.AccentOrange,
                )
            }

            SectionTitle("Top Records")
            MockVinylData.records.take(2).forEachIndexed { index, record ->
                TopRecordRow(
                    record = record,
                    plays = if (index == 0) 12 else 2,
                    averageRating = if (index == 0) "4.8" else "4.0",
                    badge = if (index == 0) "Most Played" else "Least Played",
                    badgeColor = if (index == 0) VinylColors.AccentGreen else VinylColors.AccentOrange,
                    onClick = { onOpenRecord(record.releaseId) },
                )
            }
        }
    }
}

@Composable
fun CaptureRecordScreen(
    onTakePhoto: () -> Unit,
    onUpload: () -> Unit,
    onManualSearch: () -> Unit,
) {
    ScreenContent(
        title = "Capture Record",
        subtitle = "Photograph a sleeve, barcode, or catalog area.",
    ) {
        AccentCard(borderColor = VinylColors.AccentGreen.copy(alpha = 0.35f)) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .height(260.dp)
                        .background(VinylColors.SurfaceSecondary),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "Camera preview",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
            Text(
                text = "Keep label text sharp and avoid glare for better matching.",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        GlassPrimaryButton("Take Photo", onClick = onTakePhoto)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            SecondaryButton("Upload", onClick = onUpload, modifier = Modifier.weight(1f))
            SecondaryButton("Manual Search", onClick = onManualSearch, modifier = Modifier.weight(1f))
        }
    }
}

@Composable
fun ProcessingScreen(onComplete: () -> Unit) {
    ScreenContent(
        title = "Processing",
        subtitle = "Extracting catalog clues and searching likely matches.",
    ) {
        ProcessingStep("Uploading image", "Complete", VinylColors.AccentGreen)
        ProcessingStep("Extracting text", "Active", VinylColors.AccentOrange)
        ProcessingStep("Searching candidates", "Queued", VinylColors.BorderDefault)
        GlassPrimaryButton("Show Matches", onClick = onComplete)
    }
}

@Composable
fun MatchConfirmationScreen(
    candidates: List<MatchCandidate>,
    onConfirm: (String) -> Unit,
    onManualSearch: () -> Unit,
) {
    ScreenContent(
        title = "Confirm Match",
        subtitle = "Choose the release that matches the record in hand.",
    ) {
        candidates.forEach { candidate ->
            AccentCard {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(candidate.title, color = VinylColors.TextPrimary, style = MaterialTheme.typography.titleMedium)
                        Text(candidate.artist, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
                        Text(candidate.label, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
                    }
                    ConfidenceChip(candidate.confidence)
                }
                GlassPrimaryButton("Confirm", onClick = { onConfirm(candidate.releaseId) })
            }
        }
        SecondaryButton("Manual Search", onClick = onManualSearch, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
fun ManualSearchScreen(
    records: List<RecordSummary>,
    onSelectRecord: (String) -> Unit,
) {
    var query by remember { mutableStateOf("") }

    ScreenContent(
        title = "Manual Search",
        subtitle = "Search by artist, title, label, or catalog number.",
    ) {
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Search records") },
        )
        GlassPrimaryButton("Search", onClick = {})
        records.forEach { record ->
            RecordRow(record, onClick = { onSelectRecord(record.releaseId) })
        }
    }
}

@Composable
fun SessionLoggingScreen(
    releaseId: String?,
    onSave: (String) -> Unit,
    onCancel: () -> Unit,
) {
    val record = MockVinylData.record(releaseId)
    var selectedMood by remember { mutableStateOf(MockVinylData.moods.first()) }
    var rating by remember { mutableStateOf(record.rating) }

    ScreenContent(
        title = "Log Session",
        subtitle = "${record.artist} - ${record.title}",
    ) {
        AccentCard(borderColor = VinylColors.AccentGreen.copy(alpha = 0.35f)) {
            Text(record.label, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
            Text("${record.year} - ${record.format}", color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
        }

        SectionTitle("Rating")
        RatingStars(rating)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            SecondaryButton("Lower", onClick = { rating = (rating - 1).coerceAtLeast(1) }, modifier = Modifier.weight(1f))
            SecondaryButton("Raise", onClick = { rating = (rating + 1).coerceAtMost(5) }, modifier = Modifier.weight(1f))
        }

        SectionTitle("Mood")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
        ) {
            MockVinylData.moods.take(3).forEach { mood ->
                MoodChip(
                    label = mood,
                    selected = mood == selectedMood,
                    onClick = { selectedMood = mood },
                )
            }
        }
        GlassPrimaryButton("Save Session", onClick = { onSave(record.releaseId) })
        SecondaryButton("Cancel", onClick = onCancel, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
fun RecordDetailScreen(
    releaseId: String?,
    onAddSession: (String) -> Unit,
    onHome: () -> Unit,
) {
    val record = MockVinylData.record(releaseId)

    ScreenContent(
        title = record.title,
        subtitle = record.artist,
    ) {
        AccentCard(borderColor = VinylColors.AccentPurple.copy(alpha = 0.35f)) {
            Text(
                text = "${record.label} - ${record.year}",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = "Discogs release ${record.discogsReleaseId}",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
            RatingStars(record.rating)
        }
        SectionTitle("Listening Stats")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            SnapshotCard("Sessions", "8", Modifier.weight(1f))
            SnapshotCard("Average", "${record.rating}.0", Modifier.weight(1f))
        }
        SectionTitle("History")
        MockVinylData.recentSessions
            .filter { it.releaseId == record.releaseId }
            .ifEmpty { MockVinylData.recentSessions.take(1) }
            .forEach { session -> SessionRow(session, onClick = {}) }
        GlassPrimaryButton("Add Session", onClick = { onAddSession(record.releaseId) })
        SecondaryButton("Home", onClick = onHome, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
fun PlaceholderScreen(
    title: String,
    message: String,
) {
    ScreenContent(title = title, subtitle = message) {
        AccentCard {
            Text(
                text = "Placeholder only",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}

@Composable
private fun ScreenContent(
    title: String,
    subtitle: String,
    innerPadding: PaddingValues = PaddingValues(),
    content: @Composable () -> Unit,
) {
    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = VinylSpacing.SpaceXl, vertical = VinylSpacing.Space2Xl),
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
        content()
        Spacer(Modifier.height(96.dp))
    }
}

@Composable
private fun SectionTitle(label: String) {
    Text(
        text = label,
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.titleLarge,
    )
}

@Composable
private fun SectionHeader(
    label: String,
    action: String,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SectionTitle(label)
        Text(
            text = action,
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
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
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(accentColor.copy(alpha = 0.45f)),
        )
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
    record: RecordSummary,
    plays: Int,
    averageRating: String,
    badge: String,
    badgeColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
) {
    val compact = LocalConfiguration.current.screenWidthDp < COMPACT_HOME_BREAKPOINT_DP

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
            AlbumArtBlock(accentColor = badgeColor, compact = compact)
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
                        text = "$plays plays",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = if (compact) "Avg $averageRating" else "Avg Rating: $averageRating",
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
            AlbumArtBlock(accentColor = VinylColors.AccentGreen, compact = compact)
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
                    SidePlayedChip(compact = compact)
                    RatingStars(session.rating, compact = compact)
                }
            }
            Text(
                modifier = Modifier.padding(start = VinylSpacing.SpaceSm),
                text = session.playedAt,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun SidePlayedChip(compact: Boolean) {
    Text(
        modifier =
            Modifier
                .background(VinylColors.AccentGreen, VinylColorsChipShape)
                .padding(
                    horizontal = if (compact) VinylSpacing.SpaceSm else VinylSpacing.SpaceMd,
                    vertical = if (compact) 2.dp else VinylSpacing.SpaceXs,
                ),
        text = "Side A",
        color = VinylColors.TextOnSolidAccent,
        style =
            if (compact) {
                MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp)
            } else {
                MaterialTheme.typography.bodyMedium
            },
    )
}

@Composable
private fun AlbumArtBlock(
    accentColor: androidx.compose.ui.graphics.Color,
    compact: Boolean = false,
) {
    val outerSize = if (compact) 54.dp else 64.dp
    val recordSize = if (compact) 32.dp else 38.dp
    val dotSize = if (compact) 8.dp else 9.dp
    val dotOffset = if (compact) 10.dp else 12.dp

    Box(
        modifier =
            Modifier
                .size(outerSize)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier =
                Modifier
                    .size(recordSize)
                    .background(accentColor.copy(alpha = 0.2f), CircleShape)
                    .border(1.dp, accentColor.copy(alpha = 0.45f), CircleShape),
        )
        Box(
            modifier =
                Modifier
                    .size(dotSize)
                    .offset(x = dotOffset, y = -dotOffset)
                    .background(accentColor, CircleShape),
        )
    }
}

private val VinylColorsChipShape = com.example.vinyllistenapp.ui.theme.VinylShapes.Chip

private const val COMPACT_HOME_BREAKPOINT_DP = 430

@Composable
private fun ProcessingStep(
    title: String,
    status: String,
    accent: androidx.compose.ui.graphics.Color,
) {
    AccentCard(borderColor = accent) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier =
                    Modifier
                        .size(12.dp)
                        .background(accent),
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, color = VinylColors.TextPrimary, style = MaterialTheme.typography.titleMedium)
                Text(status, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
