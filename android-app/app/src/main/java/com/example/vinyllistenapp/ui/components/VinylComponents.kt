package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.domain.ConfidenceLevel
import com.example.vinyllistenapp.domain.confidenceLevel
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun AccentCard(
    modifier: Modifier = Modifier,
    borderColor: Color = VinylColors.BorderDefault,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = VinylShapes.Card,
        color = VinylColors.SurfacePrimary,
        border = BorderStroke(1.dp, borderColor),
        content = {
            androidx.compose.foundation.layout.Column(
                modifier = Modifier.padding(VinylSpacing.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                content = content,
            )
        },
    )
}

@Composable
fun GlassPrimaryButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
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
                .fillMaxWidth()
                .height(56.dp)
                .alpha(if (enabled) 1f else 0.55f)
                .clip(VinylShapes.Button)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Button)
                .clickable(
                    enabled = enabled,
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = VinylColors.TextOnAccent,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun FloatingGlassButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val brush =
        Brush.linearGradient(
            listOf(
                VinylColors.AccentGreen.copy(alpha = 0.85f),
                VinylColors.AccentGreen.copy(alpha = 0.70f),
            ),
        )
    val glassModifier =
        modifier
            .height(56.dp)
            .shadow(
                elevation = 12.dp,
                shape = VinylShapes.Floating,
                ambientColor = VinylColors.ShadowBlack,
                spotColor = VinylColors.ShadowBlack,
            )

    Box(
        modifier =
            glassModifier
                .clip(VinylShapes.Floating)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Floating)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceXl),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = VinylColors.TextOnAccent,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun SecondaryButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(48.dp)
                .clip(VinylShapes.Button)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceLg),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun IconCircleButton(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val accessibilityLabel = accessibleControlLabel(label)

    Box(
        modifier =
            modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape)
                .semantics { contentDescription = accessibilityLabel }
                .clickable(
                    onClickLabel = accessibilityLabel,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun ConfidenceChip(
    confidence: Int,
    modifier: Modifier = Modifier,
) {
    val level = confidenceLevel(confidence)
    val fill =
        when (level) {
            ConfidenceLevel.High -> VinylColors.GreenTint20
            ConfidenceLevel.Medium -> VinylColors.OrangeTint20
            ConfidenceLevel.Low -> VinylColors.PurpleTint20
        }
    val textColor =
        when (level) {
            ConfidenceLevel.High -> VinylColors.AccentGreen
            ConfidenceLevel.Medium -> VinylColors.AccentOrange
            ConfidenceLevel.Low -> VinylColors.AccentPurple
        }

    Text(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(fill)
                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceXs),
        text = "$confidence%",
        color = textColor,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
fun MoodChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val border = if (selected) VinylColors.AccentGreen else VinylColors.BorderDefault
    val textColor = if (selected) VinylColors.AccentGreen else VinylColors.TextSecondary
    val fill = if (selected) VinylColors.GreenTint20 else VinylColors.SurfacePrimary

    Text(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(fill)
                .border(1.dp, border, VinylShapes.Chip)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        text = label,
        color = textColor,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
fun RatingStars(
    rating: Int,
    modifier: Modifier = Modifier,
    maxRating: Int = 5,
    compact: Boolean = false,
    starSize: Dp = if (compact) 14.dp else 20.dp,
    strokeWidth: Dp = if (compact) 1.5.dp else 2.dp,
    spacing: Dp = if (compact) 2.dp else VinylSpacing.SpaceXs,
    onRatingChange: ((Int) -> Unit)? = null,
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(spacing),
    ) {
        repeat(maxRating) { index ->
            RoundedRatingStar(
                filled = index < rating,
                starSize = starSize,
                strokeWidth = strokeWidth,
                onClickLabel = "Set rating to ${index + 1}",
                onClick = onRatingChange?.let { callback -> { callback(index + 1) } },
            )
        }
    }
}

@Composable
private fun RoundedRatingStar(
    filled: Boolean,
    starSize: Dp,
    strokeWidth: Dp,
    onClickLabel: String,
    onClick: (() -> Unit)?,
) {
    val color = if (filled) VinylColors.AccentOrange else VinylColors.BorderDefault
    val interactionModifier =
        if (onClick == null) {
            Modifier
        } else {
            Modifier
                .semantics { contentDescription = onClickLabel }
                .clickable(
                    onClickLabel = onClickLabel,
                    role = Role.Button,
                    onClick = onClick,
                )
        }

    Canvas(
        modifier =
            Modifier
                .size(starSize)
                .then(interactionModifier),
    ) {
        val strokeWidthPx = strokeWidth.toPx()
        val centerX = size.width / 2f
        val centerY = size.height / 2f
        val outerRadius = (minOf(size.width, size.height) - strokeWidthPx) / 2f
        val innerRadius = outerRadius * 0.48f
        val path = Path()

        repeat(10) { point ->
            val radius = if (point % 2 == 0) outerRadius else innerRadius
            val angle = -PI / 2.0 + point * PI / 5.0
            val x = centerX + cos(angle).toFloat() * radius
            val y = centerY + sin(angle).toFloat() * radius

            if (point == 0) {
                path.moveTo(x, y)
            } else {
                path.lineTo(x, y)
            }
        }
        path.close()

        if (filled) {
            drawPath(path = path, color = color)
        }
        drawPath(
            path = path,
            color = color,
            style =
                Stroke(
                    width = strokeWidthPx,
                    cap = StrokeCap.Round,
                    join = StrokeJoin.Round,
                ),
        )
    }
}

data class BottomNavItem(
    val label: String,
    val icon: ImageVector,
    val selected: Boolean,
    val onClick: () -> Unit,
)

@Composable
fun BottomNavBar(
    items: List<BottomNavItem>,
    modifier: Modifier = Modifier,
    drawTopBorder: Boolean = true,
) {
    Surface(
        modifier =
            modifier
                .fillMaxWidth()
                .drawWithContent {
                    drawContent()
                    if (drawTopBorder) {
                        drawLine(
                            color = VinylColors.BorderDefault,
                            start = Offset.Zero,
                            end = Offset(size.width, 0f),
                            strokeWidth = 1.dp.toPx(),
                        )
                    }
                },
        color = VinylColors.SurfaceSecondary,
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(
                        horizontal = VinylSpacing.SpaceLg,
                        vertical = VinylSpacing.SpaceMd,
                    ),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items.forEach { item ->
                BottomNavLabel(
                    item = item,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun RowScope.BottomNavLabel(
    item: BottomNavItem,
    modifier: Modifier = Modifier,
) {
    val color = if (item.selected) VinylColors.AccentGreen else VinylColors.TextSecondary
    Column(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .semantics { selected = item.selected }
                .clickable(
                    onClickLabel = "Open ${item.label}",
                    role = Role.Tab,
                    onClick = item.onClick,
                ).padding(vertical = VinylSpacing.SpaceXs),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Icon(
            imageVector = item.icon,
            contentDescription = null,
            tint = color,
            modifier = Modifier.size(22.dp),
        )
        Text(
            text = item.label,
            color = color,
            style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

internal fun accessibleControlLabel(label: String): String =
    when (label) {
        "X" -> "Close"
        "<" -> "Back"
        ">" -> "Next"
        "i" -> "Show information"
        else -> label
    }
