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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.ApiErrorKind
import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.api.IdentifyJobStatus
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.SUCCESS_CONFIRMATION_DELAY_MS
import com.example.vinyllistenapp.ui.components.SuccessStatusFeedback
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.delay

@Composable
fun ProcessingScreen(
    imageUri: String?,
    apiClient: VinylApiClient,
    onComplete: (List<MatchCandidate>) -> Unit,
    onManualSearch: () -> Unit,
    onDismiss: () -> Unit,
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
                            error.toIdentifyErrorMessage(),
                        )
                    return@LaunchedEffect
                }
            }
        if (candidates.isEmpty()) {
            state = IdentifyUiState.Empty
        } else {
            state = IdentifyUiState.Success(candidates)
            delay(SUCCESS_CONFIRMATION_DELAY_MS)
            onComplete(candidates)
        }
    }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(top = 48.dp, bottom = VinylSpacing.SpaceXl),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (state is IdentifyUiState.Error) {
                CloseCircleButton(onClick = onDismiss)
            } else {
                Spacer(Modifier.width(40.dp))
            }
            Text(
                modifier = Modifier.weight(1f),
                text = "Identifying Record",
                color = VinylColors.TextPrimary,
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.headlineLarge,
            )
            Spacer(Modifier.width(40.dp))
        }
        Box(
            modifier =
                Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            contentAlignment = Alignment.Center,
        ) {
            if (state is IdentifyUiState.Success) {
                SuccessStatusFeedback(message = processingSubtitle(state))
            } else {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(32.dp),
                ) {
                    ProcessingStateIndicator(state)
                    Text(
                        modifier = Modifier.width(260.dp),
                        text = processingSubtitle(state),
                        color = processingSubtitleColor(state),
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    when (state) {
                        IdentifyUiState.Empty ->
                            ProcessingRecoveryActions(
                                onRetry = { retryKey += 1 },
                                onManualSearch = onManualSearch,
                            )

                        is IdentifyUiState.Error ->
                            ProcessingRecoveryActions(
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
    ) : IdentifyUiState
}

private fun processingSubtitle(state: IdentifyUiState): String =
    when (state) {
        is IdentifyUiState.Loading -> state.status.toProcessingMessage()
        is IdentifyUiState.Success -> "Matches found"
        IdentifyUiState.Empty -> "No matches found"
        is IdentifyUiState.Error -> state.message
    }

@Composable
private fun processingSubtitleColor(state: IdentifyUiState) =
    if (state is IdentifyUiState.Error) VinylColors.AccentOrange else VinylColors.TextSecondary

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

private fun Throwable.toIdentifyErrorMessage(): String {
    val apiError = this as? ApiException ?: return "The identify request could not finish"
    return when (apiError.kind) {
        ApiErrorKind.Offline -> "The identify request could not finish"
        else -> apiError.message ?: "The identify request could not finish"
    }
}

@Composable
private fun ProcessingStateIndicator(state: IdentifyUiState) {
    when (state) {
        is IdentifyUiState.Loading -> ProcessingSpinner(animated = true)

        IdentifyUiState.Empty,
        is IdentifyUiState.Error,
        is IdentifyUiState.Success,
        -> ProcessingSpinner(animated = false)
    }
}

@Composable
private fun ProcessingRecoveryActions(
    onRetry: () -> Unit,
    onManualSearch: () -> Unit,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(32.dp),
    ) {
        ProcessingActionText(label = "Retry", onClick = onRetry)
        ProcessingActionText(label = "Manual Search", onClick = onManualSearch)
    }
}

@Composable
private fun ProcessingActionText(
    label: String,
    onClick: () -> Unit,
) {
    Text(
        modifier =
            Modifier
                .width(232.dp)
                .clickable(onClick = onClick)
                .padding(vertical = VinylSpacing.SpaceSm),
        text = label,
        color = VinylColors.AccentGreen,
        textAlign = TextAlign.Center,
        style =
            MaterialTheme.typography.bodyMedium.copy(
                fontSize = (MaterialTheme.typography.bodyMedium.fontSize.value * 1.5f).sp,
            ),
    )
}

@Composable
private fun ProcessingSpinner(animated: Boolean) {
    val rotation =
        if (animated) {
            val transition = rememberInfiniteTransition(label = "processing-spinner")
            val animatedRotation by transition.animateFloat(
                initialValue = 0f,
                targetValue = 360f,
                animationSpec =
                    infiniteRepeatable(
                        animation = tween(durationMillis = 900, easing = LinearEasing),
                        repeatMode = RepeatMode.Restart,
                    ),
                label = "processing-spinner-rotation",
            )
            animatedRotation
        } else {
            0f
        }

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
