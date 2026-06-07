package com.example.vinyllistenapp.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.graphics.vector.ImageVector
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
    Popup(
        alignment = Alignment.TopEnd,
        offset = offset,
        onDismissRequest = onDismiss,
        properties = PopupProperties(focusable = true),
    ) {
        Box(
            modifier =
                modifier
                    .width(width)
                    .shadow(8.dp, VinylShapes.Card)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.35f), VinylShapes.Card)
                    .padding(vertical = VinylSpacing.SpaceMd, horizontal = VinylSpacing.SpaceLg),
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                content = content,
            )
        }
    }
}

@Composable
fun ActionMenuAction(
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Text(
        modifier =
            modifier
                .fillMaxWidth()
                .clickable(
                    enabled = enabled,
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(vertical = VinylSpacing.SpaceXs),
        text = label,
        color = VinylColors.AccentGreen,
        textAlign = TextAlign.Center,
        style = MaterialTheme.typography.labelLarge,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
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
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            modifier = Modifier.size(18.dp),
            imageVector = icon,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
        )
        Spacer(Modifier.width(VinylSpacing.SpaceSm))
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
