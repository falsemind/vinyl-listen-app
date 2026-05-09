package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
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
                modifier = Modifier.padding(bottom = VinylSpacing.SpaceLg),
            )
        },
        floatingActionButtonPosition = FabPosition.Center,
    ) { innerPadding ->
        ScreenContent(
            title = "Vinyl Listen",
            subtitle = "Your collection is ready for the next spin.",
            innerPadding = innerPadding,
        ) {
            SectionTitle("Collection")
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                SnapshotCard("Records", MockVinylData.records.size.toString(), Modifier.weight(1f))
                SnapshotCard("Sessions", MockVinylData.recentSessions.size.toString(), Modifier.weight(1f))
            }

            SectionTitle("Recent Sessions")
            MockVinylData.recentSessions.forEach { session ->
                SessionRow(session, onClick = { onOpenRecord(session.releaseId) })
            }

            SectionTitle("Top Records")
            MockVinylData.records.forEach { record ->
                RecordRow(record, onClick = { onOpenRecord(record.releaseId) })
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
private fun SnapshotCard(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    AccentCard(modifier = modifier) {
        Text(value, color = VinylColors.AccentGreen, style = MaterialTheme.typography.titleLarge)
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
private fun SessionRow(
    session: ListeningSession,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
        borderColor = VinylColors.BorderDefault,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(session.title, color = VinylColors.TextPrimary, style = MaterialTheme.typography.titleMedium)
                Text(session.artist, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
                Text(session.playedAt, color = VinylColors.TextSecondary, style = MaterialTheme.typography.bodyMedium)
            }
            MoodChip(label = session.mood, selected = true, onClick = {})
        }
    }
}

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
