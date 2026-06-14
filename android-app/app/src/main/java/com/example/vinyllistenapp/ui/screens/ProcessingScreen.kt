package com.example.vinyllistenapp.ui.screens

import android.net.Uri
import androidx.activity.compose.BackHandler
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
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
import com.example.vinyllistenapp.data.api.IdentifyJobState
import com.example.vinyllistenapp.data.api.IdentifyJobStatus
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.ReleaseSearchResult
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.SUCCESS_CONFIRMATION_DELAY_MS
import com.example.vinyllistenapp.ui.components.SuccessStatusFeedback
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

private const val IDENTIFY_POLL_DELAY_MS = 750L
private const val BARCODE_SEARCH_TIMEOUT_MS = 10_000L

@Composable
fun BarcodeProcessingScreen(
    barcode: String?,
    apiClient: VinylApiClient,
    onComplete: (List<MatchCandidate>) -> Unit,
    onRetryScan: () -> Unit,
    onManualSearch: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var retryKey by rememberSaveable { mutableIntStateOf(0) }
    var state by remember { mutableStateOf<BarcodeProcessingUiState>(BarcodeProcessingUiState.Loading) }
    val normalizedBarcode = barcode.orEmpty()

    BackHandler(enabled = state is BarcodeProcessingUiState.Loading) {
        onDismiss()
    }

    LaunchedEffect(normalizedBarcode, retryKey) {
        state = BarcodeProcessingUiState.Loading
        if (normalizedBarcode.isBlank()) {
            state = BarcodeProcessingUiState.Error("Barcode could not be read. Retry or use Manual Search.")
            return@LaunchedEffect
        }

        val candidates =
            withTimeoutOrNull(BARCODE_SEARCH_TIMEOUT_MS) {
                runCatching {
                    apiClient
                        .searchReleases(
                            artist = null,
                            title = null,
                            catalog = null,
                            barcode = normalizedBarcode,
                            year = null,
                            limit = 10,
                            offset = 0,
                        ).results
                        .mapIndexed { index, result -> result.toBarcodeMatchCandidate(normalizedBarcode, index) }
                }.getOrElse { error ->
                    state = BarcodeProcessingUiState.Error(error.toBarcodeSearchErrorMessage())
                    null
                }
            }

        when {
            candidates == null && state is BarcodeProcessingUiState.Loading ->
                state = BarcodeProcessingUiState.Error("Barcode search timed out. Retry or use Manual Search.")

            candidates == null -> Unit
            candidates.isEmpty() -> state = BarcodeProcessingUiState.Empty
            else -> {
                state = BarcodeProcessingUiState.Success
                delay(SUCCESS_CONFIRMATION_DELAY_MS)
                onComplete(candidates)
            }
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
            CloseCircleButton(
                onClick = onDismiss,
                contentDescription = "Cancel barcode search",
            )
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
            if (state is BarcodeProcessingUiState.Success) {
                SuccessStatusFeedback(message = "Matches found")
            } else {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(32.dp),
                ) {
                    ProcessingSpinner(animated = state is BarcodeProcessingUiState.Loading)
                    Text(
                        modifier = Modifier.width(260.dp),
                        text = barcodeProcessingSubtitle(state),
                        color = if (state is BarcodeProcessingUiState.Error) VinylColors.AccentOrange else VinylColors.TextSecondary,
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    when (state) {
                        BarcodeProcessingUiState.Empty,
                        is BarcodeProcessingUiState.Error,
                        ->
                            ProcessingRecoveryActions(
                                onRetry = onRetryScan,
                                onManualSearch = { onManualSearch(normalizedBarcode) },
                            )

                        BarcodeProcessingUiState.Loading,
                        BarcodeProcessingUiState.Success,
                        -> Unit
                    }
                }
            }
        }
    }
}

@Composable
fun ProcessingScreen(
    imageUri: String?,
    apiClient: VinylApiClient,
    onComplete: (List<MatchCandidate>) -> Unit,
    onManualSearch: () -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var retryKey by rememberSaveable { mutableIntStateOf(0) }
    var state by remember(imageUri, retryKey) { mutableStateOf<IdentifyUiState>(IdentifyUiState.Loading()) }
    var currentJobId by rememberSaveable(imageUri, retryKey) { mutableStateOf<String?>(null) }
    var cancelRequested by rememberSaveable(imageUri, retryKey) { mutableStateOf(false) }

    suspend fun cancelAndLeave(jobId: String) {
        val cancelResult =
            runCatching {
                apiClient.cancelIdentifyJob(jobId)
            }.getOrElse {
                onDismiss()
                return
            }
        currentJobId = cancelResult.jobId
        when (cancelResult.status) {
            IdentifyJobStatus.Completed -> {
                val candidates = cancelResult.candidates.orEmpty()
                if (candidates.isEmpty()) {
                    onDismiss()
                } else {
                    state = IdentifyUiState.Success(candidates)
                    delay(SUCCESS_CONFIRMATION_DELAY_MS)
                    onComplete(candidates)
                }
            }

            IdentifyJobStatus.Failed,
            IdentifyJobStatus.Expired,
            IdentifyJobStatus.Canceled,
            -> onDismiss()

            else -> onDismiss()
        }
    }

    fun requestCancel() {
        if (cancelRequested) return
        cancelRequested = true
        state = IdentifyUiState.Canceling(state.currentStatus)
        val jobId = currentJobId ?: return
        scope.launch {
            cancelAndLeave(jobId)
        }
    }

    BackHandler(enabled = state.blocksBackNavigation) {
        // Active identify jobs leave through the explicit cancel action only.
    }

    LaunchedEffect(imageUri, retryKey) {
        cancelRequested = false
        state = IdentifyUiState.Loading()
        if (imageUri == null) {
            val candidates = MockVinylData.matchCandidates
            state = IdentifyUiState.Success(candidates)
            delay(SUCCESS_CONFIRMATION_DELAY_MS)
            onComplete(candidates)
            return@LaunchedEffect
        }

        val terminalJob =
            runCatching {
                var job =
                    currentJobId
                        ?.let { apiClient.getIdentifyJobStatus(it) }
                        ?: apiClient.startIdentifyJob(context, Uri.parse(imageUri))
                currentJobId = job.jobId
                if (cancelRequested) {
                    state = IdentifyUiState.Canceling(job.status)
                    cancelAndLeave(job.jobId)
                    return@LaunchedEffect
                }
                state = IdentifyUiState.Loading(job.status, job.cancelRequested)
                while (!job.status.isTerminal) {
                    delay(IDENTIFY_POLL_DELAY_MS)
                    if (cancelRequested) return@LaunchedEffect
                    job = apiClient.getIdentifyJobStatus(job.jobId)
                    currentJobId = job.jobId
                    if (cancelRequested) return@LaunchedEffect
                    state = IdentifyUiState.Loading(job.status, job.cancelRequested)
                }
                job
            }.getOrElse { error ->
                if (cancelRequested) {
                    onDismiss()
                } else {
                    state = IdentifyUiState.Error(error.toIdentifyErrorMessage())
                }
                return@LaunchedEffect
            }

        if (cancelRequested) return@LaunchedEffect
        val candidates = terminalJob.candidates.orEmpty()
        when (terminalJob.status) {
            IdentifyJobStatus.Completed -> {
                if (candidates.isEmpty()) {
                    state = IdentifyUiState.Empty
                } else {
                    state = IdentifyUiState.Success(candidates)
                    delay(SUCCESS_CONFIRMATION_DELAY_MS)
                    onComplete(candidates)
                }
            }

            IdentifyJobStatus.Failed,
            IdentifyJobStatus.Expired,
            -> state = IdentifyUiState.Error(terminalJob.toIdentifyErrorMessage())

            IdentifyJobStatus.Canceled -> state = IdentifyUiState.Canceled

            else -> state = IdentifyUiState.Empty
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
            if (state.showsTopLeftAction) {
                CloseCircleButton(
                    onClick = {
                        if (state.isCancelable) {
                            requestCancel()
                        } else {
                            onDismiss()
                        }
                    },
                    contentDescription = if (state.isCancelable) "Cancel identify" else "Close",
                )
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

                        IdentifyUiState.Canceled,
                        is IdentifyUiState.Canceling,
                        is IdentifyUiState.Loading,
                        is IdentifyUiState.Success,
                        -> Unit
                    }
                }
            }
        }
    }
}

private sealed interface IdentifyUiState {
    data class Loading(
        val status: IdentifyJobStatus? = null,
        val cancelRequested: Boolean = false,
    ) : IdentifyUiState

    data class Canceling(
        val status: IdentifyJobStatus? = null,
    ) : IdentifyUiState

    data class Success(
        val candidates: List<MatchCandidate>,
    ) : IdentifyUiState

    data object Empty : IdentifyUiState

    data object Canceled : IdentifyUiState

    data class Error(
        val message: String,
    ) : IdentifyUiState
}

private val IdentifyUiState.currentStatus: IdentifyJobStatus?
    get() =
        when (this) {
            is IdentifyUiState.Canceling -> status
            is IdentifyUiState.Loading -> status
            IdentifyUiState.Canceled,
            IdentifyUiState.Empty,
            is IdentifyUiState.Error,
            is IdentifyUiState.Success,
            -> null
        }

private val IdentifyUiState.blocksBackNavigation: Boolean
    get() = this is IdentifyUiState.Loading || this is IdentifyUiState.Canceling

private val IdentifyUiState.isCancelable: Boolean
    get() = this is IdentifyUiState.Loading || this is IdentifyUiState.Canceling

private val IdentifyUiState.showsTopLeftAction: Boolean
    get() = isCancelable || this is IdentifyUiState.Error || this is IdentifyUiState.Empty || this is IdentifyUiState.Canceled

private fun processingSubtitle(state: IdentifyUiState): String =
    when (state) {
        is IdentifyUiState.Canceling -> "Canceling identify"
        IdentifyUiState.Canceled -> "Identify canceled"
        is IdentifyUiState.Loading -> state.status.toProcessingMessage()
        is IdentifyUiState.Success -> "Matches found"
        IdentifyUiState.Empty -> "No matches found"
        is IdentifyUiState.Error -> state.message
    }

private sealed interface BarcodeProcessingUiState {
    data object Loading : BarcodeProcessingUiState

    data object Success : BarcodeProcessingUiState

    data object Empty : BarcodeProcessingUiState

    data class Error(
        val message: String,
    ) : BarcodeProcessingUiState
}

private fun barcodeProcessingSubtitle(state: BarcodeProcessingUiState): String =
    when (state) {
        BarcodeProcessingUiState.Loading -> "Searching matches..."
        BarcodeProcessingUiState.Success -> "Matches found"
        BarcodeProcessingUiState.Empty -> "No matches found"
        is BarcodeProcessingUiState.Error -> state.message
    }

private fun ReleaseSearchResult.toBarcodeMatchCandidate(
    barcode: String,
    index: Int,
): MatchCandidate =
    MatchCandidate(
        releaseId = releaseId,
        discogsReleaseId = discogsReleaseId,
        artist = artist,
        title = title,
        label = label ?: "Unknown label",
        confidence = maxOf(72, 95 - index * 4),
        year = year,
        catalogNumber = catalogNumber,
        barcode = barcode,
        coverImageUrl = thumbnailUrl,
        format = format,
        matchSource = "Barcode scan",
        matchedOn = listOf("Barcode"),
    )

private fun Throwable.toBarcodeSearchErrorMessage(): String {
    val apiError = this as? ApiException ?: return "Barcode search could not finish. Retry or use Manual Search."
    return when (apiError.kind) {
        ApiErrorKind.Offline -> "Barcode search could not finish. Retry or use Manual Search."
        else -> apiError.message ?: "Barcode search could not finish. Retry or use Manual Search."
    }
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
        IdentifyJobStatus.Canceled -> "Identify canceled"
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
        is IdentifyUiState.Canceling,
        is IdentifyUiState.Loading,
        -> ProcessingSpinner(animated = true)

        IdentifyUiState.Canceled,
        IdentifyUiState.Empty,
        is IdentifyUiState.Error,
        is IdentifyUiState.Success,
        -> ProcessingSpinner(animated = false)
    }
}

private fun IdentifyJobState.toIdentifyErrorMessage(): String =
    when (status) {
        IdentifyJobStatus.Failed -> error?.message ?: "Identify failed. Retry or use Manual Search."
        IdentifyJobStatus.Expired -> "Identify result expired. Try another image or search manually."
        else -> message.ifBlank { "The identify request could not finish" }
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
