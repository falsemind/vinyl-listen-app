package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.ScrollState
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
internal fun ScreenContent(
    title: String,
    subtitle: String,
    innerPadding: PaddingValues = PaddingValues(),
    topPadding: androidx.compose.ui.unit.Dp = VinylSpacing.Space2Xl,
    scrollState: ScrollState? = null,
    topStartContent: (@Composable () -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val contentScrollState = scrollState ?: rememberScrollState()

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(innerPadding)
                .verticalScroll(contentScrollState)
                .padding(horizontal = VinylSpacing.SpaceMd)
                .padding(top = topPadding, bottom = VinylSpacing.Space2Xl),
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
        topStartContent?.invoke()
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
internal fun ErrorRetryCard(
    message: String,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.AccentOrange.copy(alpha = 0.35f), VinylShapes.Card)
                .clickable(
                    onClickLabel = "Retry",
                    role = Role.Button,
                    onClick = onRetry,
                ).padding(VinylSpacing.SpaceLg),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = "$message Tap to retry.",
            color = VinylColors.AccentOrange,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
internal fun SectionActionHeader(
    label: String,
    action: String,
    onActionClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(
            modifier = Modifier.weight(1f),
            text = label,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            modifier =
                Modifier
                    .padding(start = VinylSpacing.SpaceMd, end = VinylSpacing.SpaceLg)
                    .clickable(
                        onClickLabel = action,
                        role = Role.Button,
                        onClick = onActionClick,
                    ),
            text = action,
            color = VinylColors.AccentGreen,
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
internal fun CircleIconButton(
    icon: ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape)
                .semantics { this.contentDescription = contentDescription }
                .clickable(
                    onClickLabel = contentDescription,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = VinylColors.TextPrimary,
            modifier = Modifier.size(20.dp),
        )
    }
}

@Composable
internal fun CloseCircleButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    contentDescription: String = "Close",
) {
    CircleIconButton(
        icon = Icons.Filled.Close,
        contentDescription = contentDescription,
        onClick = onClick,
        modifier = modifier,
    )
}

@Composable
internal fun InfoCircleButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    CircleIconButton(
        icon = Icons.Filled.Info,
        contentDescription = "Show information",
        onClick = onClick,
        modifier = modifier,
    )
}

@Composable
internal fun AlbumArtBlock(
    accentColor: androidx.compose.ui.graphics.Color,
    compact: Boolean = false,
    imageUrl: String? = null,
    contentDescription: String = "Album artwork",
) {
    val outerSize = if (compact) 54.dp else 64.dp
    val recordSize = if (compact) 32.dp else 38.dp
    val dotSize = if (compact) 8.dp else 9.dp
    val dotOffset = if (compact) 10.dp else 12.dp

    Box(
        modifier =
            Modifier
                .size(outerSize)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault),
        contentAlignment = Alignment.Center,
    ) {
        if (imageUrl.isNullOrBlank()) {
            AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset)
        } else {
            SubcomposeAsyncImage(
                model = imageUrl,
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
                loading = { AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset) },
                error = { AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset) },
            )
        }
    }
}

@Composable
private fun AlbumArtFallback(
    accentColor: androidx.compose.ui.graphics.Color,
    recordSize: androidx.compose.ui.unit.Dp,
    dotSize: androidx.compose.ui.unit.Dp,
    dotOffset: androidx.compose.ui.unit.Dp,
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

@Composable
internal fun RecordDetailAlbumArtBlock(
    imageUrl: String? = null,
    contentDescription: String = "Album artwork",
) {
    val recordSize = 56.dp
    val dotSize = 12.dp
    val dotOffset = 18.dp
    val accentColor = VinylColors.AccentGreen

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
        if (imageUrl.isNullOrBlank()) {
            AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset)
        } else {
            SubcomposeAsyncImage(
                model = imageUrl,
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
                loading = { AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset) },
                error = { AlbumArtFallback(accentColor, recordSize, dotSize, dotOffset) },
            )
        }
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
