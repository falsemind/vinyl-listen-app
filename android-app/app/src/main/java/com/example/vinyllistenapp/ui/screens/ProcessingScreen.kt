package com.example.vinyllistenapp.ui.screens

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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun ProcessingScreen(onComplete: () -> Unit) {
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
                text = "Please wait while we search our database",
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
                    ProcessingStatusCard("Uploading image", ProcessingStatus.Complete)
                    ProcessingStatusCard("Extracting text", ProcessingStatus.Complete)
                    ProcessingStatusCard(
                        label = "Searching candidates",
                        status = ProcessingStatus.Active,
                        onClick = onComplete,
                    )
                }
            }
        }
    }
}

private enum class ProcessingStatus {
    Complete,
    Active,
    Pending,
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
            ProcessingStatus.Active -> VinylColors.AccentOrange
            ProcessingStatus.Pending -> VinylColors.BorderDefault
        }
    val active = status == ProcessingStatus.Active
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
