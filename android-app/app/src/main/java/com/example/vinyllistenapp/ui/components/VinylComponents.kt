package com.example.vinyllistenapp.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
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
import androidx.compose.ui.graphics.graphicsLayer
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
import com.example.vinyllistenapp.domain.TimedSessionGroup
import com.example.vinyllistenapp.domain.confidenceLevel
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.Instant
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

enum class ScrollShortcutDirection {
    Up,
    Down,
}

@Stable
data class ScrollShortcutState(
    val visible: Boolean,
    val direction: ScrollShortcutDirection,
    val targetValue: Int,
) {
    val icon: ImageVector
        get() =
            when (direction) {
                ScrollShortcutDirection.Up -> Icons.Filled.KeyboardArrowUp
                ScrollShortcutDirection.Down -> Icons.Filled.KeyboardArrowDown
            }

    val contentDescription: String
        get() =
            when (direction) {
                ScrollShortcutDirection.Up -> "Scroll to top"
                ScrollShortcutDirection.Down -> "Scroll to bottom"
            }
}

@Composable
fun rememberScrollShortcutState(
    scrollState: ScrollState,
    headerThresholdPx: Int = 0,
): ScrollShortcutState {
    var previousScrollValue by remember { mutableIntStateOf(scrollState.value) }
    var direction by remember { mutableStateOf(ScrollShortcutDirection.Down) }
    val currentScrollValue = scrollState.value
    val maxScrollValue = scrollState.maxValue

    LaunchedEffect(currentScrollValue, maxScrollValue) {
        direction =
            when {
                currentScrollValue >= maxScrollValue && maxScrollValue > 0 -> ScrollShortcutDirection.Up
                currentScrollValue > previousScrollValue -> ScrollShortcutDirection.Down
                currentScrollValue < previousScrollValue -> ScrollShortcutDirection.Up
                else -> direction
            }
        previousScrollValue = currentScrollValue
    }

    val visible =
        maxScrollValue > 0 &&
            when (direction) {
                ScrollShortcutDirection.Up -> currentScrollValue > headerThresholdPx
                ScrollShortcutDirection.Down -> currentScrollValue < maxScrollValue
            } &&
            currentScrollValue > 0
    val targetValue =
        when (direction) {
            ScrollShortcutDirection.Up -> 0
            ScrollShortcutDirection.Down -> maxScrollValue
        }

    return ScrollShortcutState(
        visible = visible,
        direction = direction,
        targetValue = targetValue,
    )
}

@Composable
fun ScrollShortcutButton(
    scrollState: ScrollState,
    shortcutState: ScrollShortcutState,
    modifier: Modifier = Modifier,
) {
    val scope = rememberCoroutineScope()
    var longPressScrollJob by remember { mutableStateOf<Job?>(null) }

    fun stopLongPressScroll() {
        longPressScrollJob?.cancel()
        longPressScrollJob = null
    }

    fun startLongPressScroll() {
        stopLongPressScroll()
        longPressScrollJob =
            scope.launch {
                while (isActive && scrollState.value != shortcutState.targetValue) {
                    val targetValue = shortcutState.targetValue
                    val nextValue =
                        if (targetValue > scrollState.value) {
                            (scrollState.value + SCROLL_SHORTCUT_LONG_PRESS_STEP_PX).coerceAtMost(targetValue)
                        } else {
                            (scrollState.value - SCROLL_SHORTCUT_LONG_PRESS_STEP_PX).coerceAtLeast(targetValue)
                        }
                    scrollState.scrollTo(nextValue)
                    delay(SCROLL_SHORTCUT_LONG_PRESS_FRAME_MS)
                }
            }
    }

    DisposableEffect(Unit) {
        onDispose { stopLongPressScroll() }
    }

    FloatingIconButton(
        icon = shortcutState.icon,
        contentDescription = shortcutState.contentDescription,
        onClick = {
            scope.launch {
                scrollState.animateScrollTo(shortcutState.targetValue)
            }
        },
        onLongClick = ::startLongPressScroll,
        onPressEnd = ::stopLongPressScroll,
        modifier = modifier,
    )
}

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

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun FloatingIconButton(
    icon: ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onLongClick: (() -> Unit)? = null,
    onPressEnd: (() -> Unit)? = null,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val brush =
        Brush.linearGradient(
            listOf(
                VinylColors.AccentGreen.copy(alpha = 0.85f),
                VinylColors.AccentGreen.copy(alpha = 0.70f),
            ),
        )

    LaunchedEffect(isPressed) {
        if (!isPressed) {
            onPressEnd?.invoke()
        }
    }

    Box(
        modifier =
            modifier
                .size(56.dp)
                .shadow(
                    elevation = 12.dp,
                    shape = VinylShapes.Floating,
                    ambientColor = VinylColors.ShadowBlack,
                    spotColor = VinylColors.ShadowBlack,
                ).clip(VinylShapes.Floating)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Floating)
                .combinedClickable(
                    interactionSource = interactionSource,
                    indication = LocalIndication.current,
                    onClickLabel = contentDescription,
                    onLongClickLabel = contentDescription,
                    role = Role.Button,
                    onLongClick = onLongClick,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = VinylColors.TextOnAccent,
            modifier = Modifier.size(28.dp),
        )
    }
}

private const val SCROLL_SHORTCUT_LONG_PRESS_STEP_PX = 16
private const val SCROLL_SHORTCUT_LONG_PRESS_FRAME_MS = 16L

@Composable
fun TimedSessionBanner(
    sessionGroup: TimedSessionGroup,
    autoAddEnabled: Boolean,
    isStopping: Boolean,
    onAutoAddToggle: () -> Unit,
    onStop: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var nowEpochMillis by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var isExpanded by remember(sessionGroup.id) { mutableStateOf(false) }
    val arrowRotation by animateFloatAsState(
        targetValue = if (isExpanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "timedSessionBannerArrow",
    )

    LaunchedEffect(sessionGroup.id) {
        while (true) {
            nowEpochMillis = System.currentTimeMillis()
            delay(1_000)
        }
    }

    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.AccentGreen.copy(alpha = 0.14f))
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.62f), VinylShapes.Card),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(72.dp)
                    .padding(horizontal = VinylSpacing.SpaceLg),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = elapsedSessionTime(sessionGroup.startedAt, nowEpochMillis),
                    color = VinylColors.AccentGreen,
                    style = MaterialTheme.typography.titleLarge,
                )
                sessionGroup.title?.takeIf { it.isNotBlank() }?.let { title ->
                    Text(
                        text = title,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TimedSessionExpandAction(
                    arrowRotation = arrowRotation,
                    expanded = isExpanded,
                    onClick = { isExpanded = !isExpanded },
                )
                TimedSessionCircleAction(
                    icon = if (autoAddEnabled) Icons.Filled.Check else Icons.Filled.Add,
                    contentDescription = if (autoAddEnabled) "Auto-add records to timed session" else "Do not auto-add records",
                    selected = autoAddEnabled,
                    onClick = onAutoAddToggle,
                )
                TimedSessionCircleAction(
                    icon = Icons.Filled.Stop,
                    contentDescription = "Stop timed session",
                    selected = true,
                    enabled = !isStopping,
                    onClick = onStop,
                )
            }
        }
        if (isExpanded) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(VinylColors.AccentGreen.copy(alpha = 0.34f)),
            )
            TimedSessionMetadataSummaryChips(
                sessionGroup = sessionGroup,
                modifier = Modifier.padding(VinylSpacing.SpaceLg),
            )
        }
    }
}

@Composable
private fun TimedSessionExpandAction(
    arrowRotation: Float,
    expanded: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier =
            Modifier
                .size(42.dp)
                .clip(CircleShape)
                .background(Color.Transparent)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.7f), CircleShape)
                .clickable(
                    onClickLabel = if (expanded) "Collapse timed session details" else "Expand timed session details",
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.KeyboardArrowUp,
            contentDescription = null,
            tint = VinylColors.AccentGreen,
            modifier =
                Modifier
                    .size(24.dp)
                    .graphicsLayer { rotationZ = arrowRotation },
        )
    }
}

@Composable
private fun TimedSessionCircleAction(
    icon: ImageVector,
    contentDescription: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier =
            modifier
                .size(42.dp)
                .clip(CircleShape)
                .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                .border(1.dp, VinylColors.AccentGreen.copy(alpha = 0.7f), CircleShape)
                .alpha(if (enabled) 1f else 0.55f)
                .clickable(
                    enabled = enabled,
                    onClickLabel = contentDescription,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = if (selected) VinylColors.TextOnAccent else VinylColors.AccentGreen,
            modifier = Modifier.size(24.dp),
        )
    }
}

@Composable
fun TimedSessionMetadataSummaryChips(
    sessionGroup: TimedSessionGroup,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TimedSessionSummaryChip(
            text = timedSessionTypeLabel(sessionGroup.sessionType),
        )
        TimedSessionSummaryChip(
            text = timedSessionStyleFocusLabel(sessionGroup.styleFocus),
        )
        TimedSessionSummaryChip(
            text = timedSessionMoodDirectionLabel(sessionGroup.moodDirection),
        )
    }
}

@Composable
private fun TimedSessionSummaryChip(
    text: String,
    modifier: Modifier = Modifier,
) {
    Text(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.AccentGreen, VinylShapes.Chip)
                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        text = text,
        color = VinylColors.TextOnSolidAccent,
        style = MaterialTheme.typography.bodyMedium,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

fun timedSessionStyleFocusLabel(value: String): String =
    when (value) {
        "one_style" -> "One style"
        "mixed" -> "Mixed"
        "random" -> "Random"
        else -> value.toTimedSessionFallbackLabel()
    }

fun timedSessionMoodDirectionLabel(value: String): String =
    when (value) {
        "steady_mood" -> "Steady mood"
        "mood_switch" -> "Mood switch"
        "energy_build" -> "Energy build"
        "cool_down" -> "Cool down"
        else -> value.toTimedSessionFallbackLabel()
    }

fun timedSessionTypeLabel(value: String): String =
    when (value) {
        "dj_set" -> "DJ set"
        "casual_listening" -> "Casual listening"
        "rediscovery" -> "Rediscovery"
        "testing_records" -> "Testing records"
        "background" -> "Background"
        else -> value.toTimedSessionFallbackLabel()
    }

private fun String.toTimedSessionFallbackLabel(): String =
    split("_")
        .filter { it.isNotBlank() }
        .joinToString(" ") { part -> part.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() } }

private fun elapsedSessionTime(
    startedAt: String,
    nowEpochMillis: Long,
): String {
    val startedInstant =
        runCatching { Instant.parse(startedAt) }.getOrNull()
            ?: return "0:00"
    val elapsed = Duration.between(startedInstant, Instant.ofEpochMilli(nowEpochMillis)).coerceAtLeast(Duration.ZERO)
    val hours = elapsed.toHours()
    val minutes = elapsed.toMinutes() % 60
    val seconds = elapsed.seconds % 60
    return if (hours > 0) {
        "%d:%02d:%02d".format(hours, minutes, seconds)
    } else {
        "%d:%02d".format(minutes, seconds)
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
    val navigationBottomPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val bottomPadding =
        if (navigationBottomPadding > 0.dp) {
            navigationBottomPadding + VinylSpacing.SpaceXs
        } else {
            VinylSpacing.SpaceMd
        }

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
                    ).padding(
                        top = VinylSpacing.SpaceMd,
                        bottom = bottomPadding,
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
