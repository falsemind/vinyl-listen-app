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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import coil.compose.SubcomposeAsyncImage
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.components.CaptureCircleButton
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

@Composable
fun MatchConfirmationScreen(
    candidates: List<MatchCandidate>,
    apiClient: VinylApiClient,
    onConfirm: (String) -> Unit,
    onManualSearch: () -> Unit,
    onDismiss: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var detailCandidate by remember { mutableStateOf<MatchCandidate?>(null) }
    var confirmingDiscogsId by remember { mutableStateOf<Long?>(null) }
    var confirmError by remember { mutableStateOf<String?>(null) }

    fun confirmCandidate(candidate: MatchCandidate) {
        candidate.releaseId?.let {
            onConfirm(it)
            return
        }
        confirmingDiscogsId = candidate.discogsReleaseId
        confirmError = null
        scope.launch {
            runCatching { apiClient.importRelease(candidate.discogsReleaseId) }
                .onSuccess { releaseId -> onConfirm(releaseId) }
                .onFailure { error ->
                    confirmError = error.toUserMessage("Could not prepare this release. Retry or use Manual Search.")
                    confirmingDiscogsId = null
                }
        }
    }

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(horizontal = VinylSpacing.SpaceMd),
        ) {
            MatchConfirmationHeader(onDismiss = onDismiss)
            Text(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(bottom = VinylSpacing.SpaceXl),
                text = "Select the correct release from the matches below",
                color = VinylColors.TextSecondary,
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.bodyLarge,
            )
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
            ) {
                confirmError?.let { message ->
                    Text(
                        text = message,
                        color = VinylColors.AccentOrange,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                candidates.forEachIndexed { index, candidate ->
                    val record =
                        candidate.releaseId?.let { MockVinylData.record(it) }
                            ?: MockVinylData.recordByDiscogsId(candidate.discogsReleaseId)
                    MatchCandidateCard(
                        candidate = candidate,
                        year = candidate.year ?: record?.year,
                        catalogNumber =
                            candidate.catalogNumber
                                ?: record?.catalogNumber
                                ?: matchCatalogNumber(candidate.releaseId ?: candidate.discogsReleaseId.toString(), index),
                        isConfirming = confirmingDiscogsId == candidate.discogsReleaseId,
                        onConfirm = { confirmCandidate(candidate) },
                        onDetails = { detailCandidate = candidate },
                    )
                }
                Spacer(Modifier.height(VinylSpacing.SpaceSm))
            }
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(top = VinylSpacing.SpaceLg, bottom = 32.dp),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
            ) {
                MatchFooterAction(
                    label = "Show More\nMatches",
                    accentColor = VinylColors.AccentGreen,
                    onClick = {},
                    modifier = Modifier.weight(1f),
                )
                MatchFooterAction(
                    label = "Manual Search",
                    accentColor = VinylColors.AccentOrange,
                    onClick = onManualSearch,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        detailCandidate?.let { candidate ->
            MatchDetailsPlaceholderPopup(
                candidate = candidate,
                onDismiss = { detailCandidate = null },
            )
        }
    }
}

@Composable
private fun MatchConfirmationHeader(onDismiss: () -> Unit) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceXl),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CaptureCircleButton(label = "X", onClick = onDismiss)
        Text(
            text = "Confirm Match",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleLarge,
        )
        Spacer(Modifier.width(40.dp))
    }
}

@Composable
private fun MatchCandidateCard(
    candidate: MatchCandidate,
    year: Int?,
    catalogNumber: String,
    isConfirming: Boolean,
    onConfirm: () -> Unit,
    onDetails: () -> Unit,
) {
    val accentColor = matchConfidenceColor(candidate.confidence)

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, accentColor.copy(alpha = 0.35f), VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top,
            ) {
                MatchAlbumArtBlock(
                    accentColor = accentColor,
                    imageUrl = candidate.coverImageUrl,
                    contentDescription = "${candidate.title} cover art",
                )
                Spacer(Modifier.width(VinylSpacing.SpaceLg))
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top,
                    ) {
                        Column(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
                        ) {
                            Text(
                                text = candidate.artist,
                                color = VinylColors.TextPrimary,
                                style = MaterialTheme.typography.titleMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = candidate.title,
                                color = VinylColors.TextSecondary,
                                style = MaterialTheme.typography.bodyLarge,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        MatchConfidenceBadge(confidence = candidate.confidence)
                    }
                    Spacer(Modifier.height(VinylSpacing.SpaceSm))
                    MatchMetadataRow(label = "Year:", value = year?.toString() ?: "Unknown")
                    MatchMetadataRow(label = "Label:", value = candidate.label)
                    MatchMetadataRow(label = "Cat#:", value = catalogNumber)
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                MatchConfirmButton(
                    onClick = onConfirm,
                    enabled = !isConfirming,
                    label = if (isConfirming) "Importing" else "Confirm",
                    modifier = Modifier.weight(1f),
                )
                MatchDetailsButton(onClick = onDetails, modifier = Modifier.width(64.dp))
            }
        }
    }
}

@Composable
private fun MatchDetailsPlaceholderPopup(
    candidate: MatchCandidate,
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
                    .border(1.dp, matchConfidenceColor(candidate.confidence).copy(alpha = 0.35f), VinylShapes.Card)
                    .padding(VinylSpacing.SpaceLg),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
                Text(
                    text = "Release Details",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = "${candidate.artist} - ${candidate.title}",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    text =
                        listOfNotNull(
                            candidate.year?.let { "Year: $it" },
                            candidate.catalogNumber?.let { "Cat#: $it" },
                            candidate.barcode?.let { "Barcode: $it" },
                            candidate.matchSource?.let { "Source: $it" },
                            candidate.matchedOn.takeIf { it.isNotEmpty() }?.joinToString(prefix = "Matched: "),
                        ).ifEmpty { listOf("No extra metadata returned for this candidate.") }.joinToString("\n"),
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun MatchAlbumArtBlock(
    accentColor: androidx.compose.ui.graphics.Color,
    imageUrl: String?,
    contentDescription: String,
) {
    Box(
        modifier =
            Modifier
                .size(80.dp)
                .clip(VinylShapes.Card)
                .background(
                    Brush.linearGradient(
                        listOf(
                            accentColor.copy(alpha = 0.48f),
                            VinylColors.SurfaceSecondary,
                            VinylColors.SurfacePrimary,
                        ),
                    ),
                ),
        contentAlignment = Alignment.Center,
    ) {
        if (imageUrl.isNullOrBlank()) {
            MatchAlbumArtFallback(accentColor)
        } else {
            SubcomposeAsyncImage(
                model = imageUrl,
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
                loading = { MatchAlbumArtFallback(accentColor) },
                error = { MatchAlbumArtFallback(accentColor) },
            )
        }
    }
}

@Composable
private fun MatchAlbumArtFallback(accentColor: androidx.compose.ui.graphics.Color) {
    Box(
        modifier =
            Modifier
                .size(46.dp)
                .background(accentColor.copy(alpha = 0.20f), CircleShape)
                .border(1.dp, accentColor.copy(alpha = 0.50f), CircleShape),
    )
    Box(
        modifier =
            Modifier
                .size(10.dp)
                .offset(x = 14.dp, y = -14.dp)
                .background(accentColor, CircleShape),
    )
}

@Composable
private fun MatchConfidenceBadge(confidence: Int) {
    val accentColor = matchConfidenceColor(confidence)
    Text(
        modifier =
            Modifier
                .clip(VinylShapes.Chip)
                .background(accentColor.copy(alpha = 0.20f))
                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceXs),
        text = matchConfidenceLabel(confidence),
        color = accentColor,
        style = MaterialTheme.typography.bodyMedium,
        maxLines = 1,
    )
}

@Composable
private fun MatchMetadataRow(
    label: String,
    value: String,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            modifier = Modifier.weight(1f),
            text = value,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun MatchConfirmButton(
    onClick: () -> Unit,
    enabled: Boolean,
    label: String,
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
                .height(56.dp)
                .clip(VinylShapes.Button)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Button)
                .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "✓",
                color = VinylColors.TextOnAccent,
                style = MaterialTheme.typography.labelLarge,
            )
            Text(
                text = label,
                color = VinylColors.TextOnAccent,
                style = MaterialTheme.typography.labelLarge,
            )
        }
    }
}

@Composable
private fun MatchDetailsButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(56.dp)
                .clip(VinylShapes.Button)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = ">",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun MatchFooterAction(
    label: String,
    accentColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(66.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .clickable(onClick = onClick)
                .padding(horizontal = VinylSpacing.SpaceMd),
        contentAlignment = Alignment.Center,
    ) {
        CardTopAccentLine(
            accentColor = accentColor,
            alpha = 0.30f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Text(
            text = label,
            color = VinylColors.TextPrimary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

private fun matchConfidenceColor(confidence: Int): androidx.compose.ui.graphics.Color =
    when {
        confidence >= 85 -> VinylColors.AccentGreen
        confidence >= 70 -> VinylColors.AccentOrange
        else -> VinylColors.AccentPurple
    }

private fun matchConfidenceLabel(confidence: Int): String =
    when {
        confidence >= 85 -> "High"
        confidence >= 70 -> "Medium"
        else -> "Low"
    }
