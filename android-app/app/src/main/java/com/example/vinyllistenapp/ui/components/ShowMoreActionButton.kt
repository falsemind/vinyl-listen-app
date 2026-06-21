package com.example.vinyllistenapp.ui.components

import androidx.compose.animation.core.animateIntAsState
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

const val SHOW_MORE_MAX_COUNT = 250

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ShowMoreActionButton(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
    onCustomCount: (Int) -> Unit,
    modifier: Modifier = Modifier,
    width: Dp = 232.dp,
) {
    var inputVisible by rememberSaveable { mutableStateOf(false) }
    var inputValue by rememberSaveable { mutableStateOf("") }
    val density = LocalDensity.current
    val keyboardController = LocalSoftwareKeyboardController.current
    val keyboardBottom = WindowInsets.ime.getBottom(density)
    val inputPopupYOffset by animateIntAsState(
        targetValue =
            if (keyboardBottom > 0) {
                -keyboardBottom - with(density) { VinylSpacing.SpaceMd.roundToPx() }
            } else {
                0
            },
        label = "show-more-input-offset",
    )

    fun dismissInput() {
        keyboardController?.hide()
        inputVisible = false
    }

    Box(
        modifier = modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceSm),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                modifier =
                    Modifier
                        .width(width)
                        .combinedClickable(
                            enabled = enabled,
                            onClickLabel = label,
                            onLongClickLabel = "Choose item count",
                            role = Role.Button,
                            onLongClick = {
                                inputValue = ""
                                inputVisible = true
                            },
                            onClick = onClick,
                        ),
                text = label,
                color = VinylColors.AccentGreen,
                textAlign = TextAlign.Center,
                style =
                    MaterialTheme.typography.bodyMedium.copy(
                        fontSize = (MaterialTheme.typography.bodyMedium.fontSize.value * 1.5f).sp,
                    ),
            )
            Text(
                modifier =
                    Modifier
                        .width(width)
                        .padding(top = VinylSpacing.SpaceXs),
                text = "Tap and hold to load custom amount of items (from 1 to 250)",
                color = VinylColors.TextSecondary,
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (inputVisible) {
            Popup(
                alignment = Alignment.Center,
                offset = IntOffset(x = 0, y = inputPopupYOffset),
                onDismissRequest = { dismissInput() },
                properties = PopupProperties(focusable = true),
            ) {
                ShowMoreCountInput(
                    value = inputValue,
                    onValueChange = { inputValue = sanitizeShowMoreCount(it) },
                    onDismiss = { dismissInput() },
                    onSave = {
                        inputValue.toIntOrNull()?.coerceIn(1, SHOW_MORE_MAX_COUNT)?.let(onCustomCount)
                        dismissInput()
                        inputValue = ""
                    },
                    width = width,
                )
            }
        }
    }
}

@Composable
private fun ShowMoreCountInput(
    value: String,
    onValueChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onSave: () -> Unit,
    width: Dp,
) {
    val count = value.toIntOrNull()
    val canSave = count != null && count in 1..SHOW_MORE_MAX_COUNT
    val focusRequester = remember { FocusRequester() }
    val keyboardController = LocalSoftwareKeyboardController.current

    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
        keyboardController?.show()
    }

    Row(
        modifier =
            Modifier
                .width(width)
                .height(64.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(start = VinylSpacing.SpaceLg, end = VinylSpacing.SpaceSm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            modifier =
                Modifier
                    .weight(1f)
                    .focusRequester(focusRequester),
            singleLine = true,
            keyboardOptions =
                KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done,
                ),
            keyboardActions =
                KeyboardActions(
                    onDone = {
                        if (canSave) {
                            onSave()
                        }
                    },
                ),
            textStyle =
                MaterialTheme.typography.bodyMedium.copy(
                    color = VinylColors.TextPrimary,
                ),
            cursorBrush = SolidColor(VinylColors.AccentGreen),
            decorationBox = { innerTextField ->
                if (value.isBlank()) {
                    Text(
                        text = "Items to load",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                innerTextField()
            },
        )
        Icon(
            modifier =
                Modifier
                    .size(40.dp)
                    .clip(VinylShapes.Chip)
                    .clickable(
                        onClickLabel = if (canSave) "Load custom count" else "Dismiss custom count input",
                        role = Role.Button,
                        onClick = { if (canSave) onSave() else onDismiss() },
                    ).padding(VinylSpacing.SpaceSm),
            imageVector = if (canSave) Icons.Filled.Check else Icons.Filled.Close,
            contentDescription = null,
            tint = if (canSave) VinylColors.AccentGreen else VinylColors.TextSecondary,
        )
    }
}

private fun sanitizeShowMoreCount(value: String): String {
    val digits = value.filter { it.isDigit() }.take(SHOW_MORE_MAX_COUNT.toString().length)
    return digits
        .toIntOrNull()
        ?.coerceAtMost(SHOW_MORE_MAX_COUNT)
        ?.toString()
        ?: digits
}
