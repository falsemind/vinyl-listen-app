package com.example.vinyllistenapp.ui.screens

import android.net.Uri
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.api.IdentifyJobStatus
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.delay

@Composable
fun ProcessingScreen(
    imageUri: String?,
    apiClient: VinylApiClient,
    onComplete: (List<MatchCandidate>) -> Unit,
    onManualSearch: () -> Unit,
) {
    val context = LocalContext.current
    var retryKey by remember { mutableIntStateOf(0) }
    var state by remember(imageUri, retryKey) { mutableStateOf<IdentifyUiState>(IdentifyUiState.Loading()) }

    LaunchedEffect(imageUri, retryKey) {
        state = IdentifyUiState.Loading()
        val candidates =
            if (imageUri == null) {
                MockVinylData.matchCandidates
            } else {
                runCatching {
                    apiClient.identifyImage(context, Uri.parse(imageUri)) { job ->
                        state = IdentifyUiState.Loading(job.status)
                    }
                }.getOrElse { error ->
                    state =
                        IdentifyUiState.Error(
                            error.toUserMessage("Identify failed. Retry or use Manual Search."),
                            error.toProcessingFailureStep(),
                        )
                    return@LaunchedEffect
                }
            }
        if (candidates.isEmpty()) {
            state = IdentifyUiState.Empty
        } else {
            state = IdentifyUiState.Success(candidates)
            delay(450)
            onComplete(candidates)
        }
    }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceXl),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(top = 48.dp, bottom = VinylSpacing.SpaceXl),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        ) {
            Text(
                text = "Identifying Record",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineLarge,
            )
            Text(
                text = processingSubtitle(state),
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Box(
            modifier =
                Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(48.dp),
            ) {
                ProcessingSpinner()
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
                ) {
                    ProcessingStatusCard("Uploading image", uploadStatus(state))
                    ProcessingStatusCard(
                        label = "Extracting text",
                        status = extractingStatus(state),
                    )
                    ProcessingStatusCard(
                        label = "Searching candidates",
                        status = searchingStatus(state),
                    )
                    when (val currentState = state) {
                        IdentifyUiState.Empty ->
                            ProcessingRecoveryActions(
                                message = "No matches found.",
                                onRetry = { retryKey += 1 },
                                onManualSearch = onManualSearch,
                            )

                        is IdentifyUiState.Error ->
                            ProcessingRecoveryActions(
                                message = currentState.message,
                                onRetry = { retryKey += 1 },
                                onManualSearch = onManualSearch,
                            )

                        is IdentifyUiState.Loading, is IdentifyUiState.Success -> Unit
                    }
                }
            }
        }
    }
}

private sealed interface IdentifyUiState {
    data class Loading(
        val status: IdentifyJobStatus? = null,
    ) : IdentifyUiState

    data class Success(
        val candidates: List<MatchCandidate>,
    ) : IdentifyUiState

    data object Empty : IdentifyUiState

    data class Error(
        val message: String,
        val failedStep: ProcessingFailureStep,
    ) : IdentifyUiState
}

private enum class ProcessingFailureStep {
    Upload,
    Extract,
    Search,
}

private fun processingSubtitle(state: IdentifyUiState): String =
    when (state) {
        is IdentifyUiState.Loading -> state.status.toProcessingMessage()
        is IdentifyUiState.Success -> "Matches found"
        IdentifyUiState.Empty -> "Try another image or search manually"
        is IdentifyUiState.Error -> "The identify request could not finish"
    }

private enum class ProcessingStatus {
    Complete,
    Active,
    Error,
    Pending,
}

private fun uploadStatus(state: IdentifyUiState): ProcessingStatus =
    when (state) {
        is IdentifyUiState.Loading ->
            if (state.status == null || state.status == IdentifyJobStatus.Queued) {
                ProcessingStatus.Active
            } else {
                ProcessingStatus.Complete
            }

        is IdentifyUiState.Error ->
            if (state.failedStep == ProcessingFailureStep.Upload) ProcessingStatus.Error else ProcessingStatus.Complete

        IdentifyUiState.Empty,
        is IdentifyUiState.Success,
        -> ProcessingStatus.Complete
    }

private fun extractingStatus(state: IdentifyUiState): ProcessingStatus =
    when (state) {
        is IdentifyUiState.Loading ->
            when (state.status) {
                IdentifyJobStatus.PreprocessingImage,
                IdentifyJobStatus.ExtractingText,
                IdentifyJobStatus.ParsingIdentifiers,
                -> ProcessingStatus.Active

                IdentifyJobStatus.SearchingLocal,
                IdentifyJobStatus.SearchingDiscogs,
                IdentifyJobStatus.RankingCandidates,
                IdentifyJobStatus.Completed,
                -> ProcessingStatus.Complete

                else -> ProcessingStatus.Pending
            }

        is IdentifyUiState.Error ->
            if (state.failedStep == ProcessingFailureStep.Extract) ProcessingStatus.Error else ProcessingStatus.Pending

        IdentifyUiState.Empty,
        is IdentifyUiState.Success,
        -> ProcessingStatus.Complete
    }

private fun searchingStatus(state: IdentifyUiState): ProcessingStatus =
    when (state) {
        is IdentifyUiState.Loading ->
            when (state.status) {
                IdentifyJobStatus.SearchingLocal,
                IdentifyJobStatus.SearchingDiscogs,
                IdentifyJobStatus.RankingCandidates,
                -> ProcessingStatus.Active

                IdentifyJobStatus.Completed -> ProcessingStatus.Complete
                else -> ProcessingStatus.Pending
            }

        IdentifyUiState.Empty -> ProcessingStatus.Error
        is IdentifyUiState.Error ->
            if (state.failedStep == ProcessingFailureStep.Search) ProcessingStatus.Error else ProcessingStatus.Pending

        is IdentifyUiState.Success -> ProcessingStatus.Active
    }

private fun IdentifyJobStatus?.toProcessingMessage(): String =
    when (this) {
        null,
        IdentifyJobStatus.Queued,
        -> "Uploading image"

        IdentifyJobStatus.UploadReceived -> "Image received by server"
        IdentifyJobStatus.PreprocessingImage -> "Preparing image"
        IdentifyJobStatus.ExtractingText -> "Extracting text"
        IdentifyJobStatus.ParsingIdentifiers -> "Reading label details"
        IdentifyJobStatus.SearchingLocal -> "Checking local records"
        IdentifyJobStatus.SearchingDiscogs -> "Searching Discogs candidates"
        IdentifyJobStatus.RankingCandidates -> "Ranking matches"
        IdentifyJobStatus.Completed -> "Matches found"
        IdentifyJobStatus.Failed -> "The identify request could not finish"
        IdentifyJobStatus.Expired -> "Identify result expired"
        IdentifyJobStatus.Unknown -> "Identifying record"
    }

private fun Throwable.toProcessingFailureStep(): ProcessingFailureStep =
    when ((this as? ApiException)?.failedStep) {
        "upload" -> ProcessingFailureStep.Upload
        "extract" -> ProcessingFailureStep.Extract
        "search" -> ProcessingFailureStep.Search
        else -> ProcessingFailureStep.Search
    }

@Composable
private fun ProcessingRecoveryActions(
    message: String,
    onRetry: () -> Unit,
    onManualSearch: () -> Unit,
) {
    Text(
        modifier = Modifier.width(260.dp),
        text = message,
        color = VinylColors.AccentOrange,
        style = MaterialTheme.typography.bodyMedium,
        maxLines = 3,
        overflow = TextOverflow.Ellipsis,
    )
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
    ) {
        ProcessingStatusCard(
            label = "Retry",
            status = ProcessingStatus.Active,
            onClick = onRetry,
        )
        ProcessingStatusCard(
            label = "Manual Search",
            status = ProcessingStatus.Active,
            onClick = onManualSearch,
        )
    }
}

@Composable
private fun ProcessingSpinner() {
    val transition = rememberInfiniteTransition(label = "processing-spinner")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec =
            infiniteRepeatable(
                animation = tween(durationMillis = 900, easing = LinearEasing),
                repeatMode = RepeatMode.Restart,
            ),
        label = "processing-spinner-rotation",
    )

    Canvas(
        modifier =
            Modifier
                .size(100.dp)
                .rotate(rotation),
    ) {
        drawArc(
            color = VinylColors.AccentGreen,
            startAngle = -90f,
            sweepAngle = 285f,
            useCenter = false,
            style =
                Stroke(
                    width = 6.dp.toPx(),
                    cap = StrokeCap.Round,
                ),
        )
    }
}

@Composable
private fun ProcessingStatusCard(
    label: String,
    status: ProcessingStatus,
    onClick: (() -> Unit)? = null,
) {
    val accent =
        when (status) {
            ProcessingStatus.Complete -> VinylColors.AccentGreen
            ProcessingStatus.Active,
            ProcessingStatus.Error,
            -> VinylColors.AccentOrange

            ProcessingStatus.Pending -> VinylColors.BorderDefault
        }
    val active = status == ProcessingStatus.Active || status == ProcessingStatus.Error
    val emphasized = status != ProcessingStatus.Pending
    var cardModifier =
        Modifier
            .width(if (active) 232.dp else 212.dp)
            .clip(VinylShapes.Card)
            .background(VinylColors.SurfacePrimary)
            .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)

    if (onClick != null) {
        cardModifier = cardModifier.clickable(onClick = onClick)
    }

    Box(
        modifier =
            cardModifier.padding(
                horizontal = VinylSpacing.SpaceLg,
                vertical = VinylSpacing.SpaceMd,
            ),
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ProcessingStatusDot(status = status, accent = accent)
            Text(
                text = label,
                color = if (emphasized) VinylColors.TextPrimary else VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun ProcessingStatusDot(
    status: ProcessingStatus,
    accent: androidx.compose.ui.graphics.Color,
) {
    Box(
        modifier =
            Modifier
                .size(20.dp)
                .background(accent, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        when (status) {
            ProcessingStatus.Complete ->
                Text(
                    text = "✓",
                    color = VinylColors.TextOnSolidAccent,
                    style = MaterialTheme.typography.bodyMedium,
                )

            ProcessingStatus.Active ->
                Canvas(modifier = Modifier.size(12.dp)) {
                    drawArc(
                        color = VinylColors.TextOnSolidAccent,
                        startAngle = -90f,
                        sweepAngle = 270f,
                        useCenter = false,
                        style =
                            Stroke(
                                width = 2.dp.toPx(),
                                cap = StrokeCap.Round,
                            ),
                    )
                }

            ProcessingStatus.Error ->
                Text(
                    text = "!",
                    color = VinylColors.TextOnSolidAccent,
                    style = MaterialTheme.typography.bodyMedium,
                )

            ProcessingStatus.Pending -> Unit
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
