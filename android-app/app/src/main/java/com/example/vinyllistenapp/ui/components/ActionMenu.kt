package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun ActionMenuToggle(
    isOpen: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Icon(
        modifier =
            modifier
                .size(44.dp)
                .clip(CircleShape)
                .clickable(
                    onClickLabel = if (isOpen) "Close menu" else "Open menu",
                    role = Role.Button,
                    onClick = onClick,
                ).padding(VinylSpacing.SpaceSm),
        imageVector = if (isOpen) Icons.Filled.Close else Icons.Filled.Menu,
        contentDescription = if (isOpen) "Close menu" else "Open menu",
        tint = VinylColors.AccentGreen,
    )
}

@Composable
fun ActionMenuPopup(
    offset: IntOffset,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
    width: Dp = 260.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val scrollState = rememberScrollState()
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current
    val maxPopupHeight =
        with(density) {
            (configuration.screenHeightDp.dp - offset.y.toDp() - VinylSpacing.SpaceLg)
                .coerceAtLeast(240.dp)
        }
    val shouldShowScrollbar = scrollState.maxValue > 0
    Popup(
        alignment = Alignment.TopEnd,
        offset = offset,
        onDismissRequest = onDismiss,
        properties = PopupProperties(focusable = false),
    ) {
        Box(
            modifier =
                modifier
                    .width(width)
                    .heightIn(max = maxPopupHeight)
                    .shadow(8.dp, VinylShapes.Card)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.35f), VinylShapes.Card)
                    .padding(vertical = VinylSpacing.SpaceMd, horizontal = VinylSpacing.SpaceLg),
        ) {
            Column(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .verticalScroll(scrollState)
                        .padding(end = if (shouldShowScrollbar) VinylSpacing.SpaceSm else 0.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                content = content,
            )
            if (shouldShowScrollbar) {
                ActionMenuScrollIndicator(
                    scrollState = scrollState,
                    modifier =
                        Modifier
                            .align(Alignment.CenterEnd)
                            .fillMaxHeight()
                            .width(2.dp),
                )
            }
        }
    }
}

@Composable
private fun ActionMenuScrollIndicator(
    scrollState: ScrollState,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val trackHeight = size.height
        if (trackHeight <= 0f || scrollState.maxValue <= 0) {
            return@Canvas
        }

        val totalContentHeight = trackHeight + scrollState.maxValue
        val minThumbHeight = 24.dp.toPx().coerceAtMost(trackHeight)
        val thumbHeight =
            (trackHeight * trackHeight / totalContentHeight)
                .coerceIn(minThumbHeight, trackHeight)
        val scrollFraction = scrollState.value / scrollState.maxValue.toFloat()
        val thumbTop = (trackHeight - thumbHeight) * scrollFraction
        val cornerRadius = CornerRadius(size.width / 2f, size.width / 2f)

        drawRoundRect(
            color = VinylColors.AccentGreen.copy(alpha = 0.18f),
            topLeft = Offset.Zero,
            size = Size(size.width, trackHeight),
            cornerRadius = cornerRadius,
        )
        drawRoundRect(
            color = VinylColors.AccentGreen.copy(alpha = 0.72f),
            topLeft = Offset(0f, thumbTop),
            size = Size(size.width, thumbHeight),
            cornerRadius = cornerRadius,
        )
    }
}

@Composable
fun ActionMenuAction(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
    iconTint: Color = VinylColors.AccentGreen,
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .clickable(
                    enabled = enabled,
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(vertical = VinylSpacing.SpaceXs),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            modifier =
                Modifier
                    .weight(1f)
                    .padding(end = VinylSpacing.SpaceSm),
            text = label,
            color = VinylColors.AccentGreen,
            textAlign = TextAlign.Start,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        icon?.let {
            Icon(
                modifier = Modifier.size(18.dp),
                imageVector = it,
                contentDescription = null,
                tint = iconTint,
            )
        }
    }
}

@Composable
fun ActionMenuStatus(
    label: String,
    modifier: Modifier = Modifier,
    icon: ImageVector = Icons.Filled.Check,
) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(vertical = VinylSpacing.SpaceXs),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            modifier =
                Modifier
                    .weight(1f)
                    .padding(end = VinylSpacing.SpaceSm),
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Icon(
            modifier = Modifier.size(18.dp),
            imageVector = icon,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
        )
    }
}
