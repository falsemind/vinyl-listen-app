package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.domain.ConfidenceLevel
import com.example.vinyllistenapp.domain.confidenceLevel
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

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
                .clip(VinylShapes.Button)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Button)
                .clickable(onClick = onClick),
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
                VinylColors.AccentGreen.copy(alpha = 0.75f),
                VinylColors.AccentGreen.copy(alpha = 0.60f),
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
                .clickable(onClick = onClick)
                .padding(horizontal = VinylSpacing.SpaceXl),
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
                .clickable(onClick = onClick)
                .padding(horizontal = VinylSpacing.SpaceLg),
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
    Box(
        modifier =
            modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(VinylColors.SurfaceSecondary)
                .border(1.dp, VinylColors.BorderDefault, CircleShape)
                .clickable(onClick = onClick),
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
                .clickable(onClick = onClick)
                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
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
) {
    val starStyle =
        if (compact) {
            MaterialTheme.typography.bodyMedium.copy(fontSize = 14.sp, lineHeight = 16.sp)
        } else {
            MaterialTheme.typography.titleMedium
        }

    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(if (compact) 2.dp else VinylSpacing.SpaceXs),
    ) {
        repeat(maxRating) { index ->
            Text(
                text = if (index < rating) "★" else "☆",
                color = if (index < rating) VinylColors.AccentOrange else VinylColors.TextSecondary,
                style = starStyle,
            )
        }
    }
}

data class BottomNavItem(
    val label: String,
    val selected: Boolean,
    val onClick: () -> Unit,
)

@Composable
fun BottomNavBar(
    items: List<BottomNavItem>,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = VinylColors.SurfaceSecondary,
        border = BorderStroke(1.dp, VinylColors.BorderDefault),
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
                BottomNavLabel(item)
            }
        }
    }
}

@Composable
private fun RowScope.BottomNavLabel(item: BottomNavItem) {
    Text(
        modifier =
            Modifier
                .weight(1f)
                .clip(VinylShapes.Chip)
                .clickable(onClick = item.onClick)
                .padding(vertical = VinylSpacing.SpaceSm),
        text = item.label,
        color = if (item.selected) VinylColors.AccentGreen else VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodyMedium,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}
