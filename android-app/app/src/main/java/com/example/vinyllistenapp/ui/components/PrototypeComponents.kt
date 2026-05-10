package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
internal fun ScreenContent(
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
internal fun SectionTitle(label: String) {
    Text(
        text = label,
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.titleLarge,
    )
}

@Composable
internal fun CaptureCircleButton(
    label: String,
    onClick: () -> Unit,
) {
    Box(
        modifier =
            Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape)
                .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = if (label == "X") VinylColors.TextPrimary else VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
internal fun AlbumArtBlock(
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

@Composable
internal fun RecordDetailAlbumArtBlock() {
    Box(
        modifier =
            Modifier
                .size(96.dp)
                .clip(VinylShapes.Card)
                .background(
                    Brush.linearGradient(
                        listOf(
                            VinylColors.AccentPurple.copy(alpha = 0.42f),
                            VinylColors.SurfaceSecondary,
                            VinylColors.AccentGreen.copy(alpha = 0.26f),
                        ),
                    ),
                ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier =
                Modifier
                    .size(56.dp)
                    .background(VinylColors.AccentGreen.copy(alpha = 0.18f), CircleShape)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.45f), CircleShape),
        )
        Box(
            modifier =
                Modifier
                    .size(12.dp)
                    .offset(x = 18.dp, y = -18.dp)
                    .background(VinylColors.AccentOrange, CircleShape),
        )
    }
}

@Composable
internal fun CardTopAccentLine(
    accentColor: androidx.compose.ui.graphics.Color,
    alpha: Float,
    modifier: Modifier = Modifier,
) {
    if (SHOW_CARD_TOP_ACCENTS) {
        Box(
            modifier =
                modifier
                    .fillMaxWidth()
                    .height(1.dp)
                    .background(
                        Brush.linearGradient(
                            listOf(
                                androidx.compose.ui.graphics.Color.Transparent,
                                accentColor.copy(alpha = alpha),
                                androidx.compose.ui.graphics.Color.Transparent,
                            ),
                        ),
                    ),
        )
    }
}

private const val SHOW_CARD_TOP_ACCENTS = false
