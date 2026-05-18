package com.example.vinyllistenapp.ui.screens

import androidx.compose.animation.core.animateIntAsState
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseSideOption
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.RatingStars
import com.example.vinyllistenapp.ui.components.RecordDetailAlbumArtBlock
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

private const val CUSTOM_MOOD_MIN_LENGTH = 3
private const val CUSTOM_MOOD_MAX_LENGTH = 20
internal val BUILT_IN_SESSION_MOODS = listOf("Energetic", "Calm", "Melancholic", "Nostalgic", "Focused", "Background")

@Composable
fun SessionLoggingScreen(
    releaseId: String?,
    apiClient: VinylApiClient,
    onSave: (String) -> Unit,
    onCancel: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val fallbackRecord = MockVinylData.record(releaseId)
    var loadedRecord by remember(releaseId) { mutableStateOf<RecordSummary?>(null) }
    val record = loadedRecord ?: fallbackRecord
    val sideOptions = sessionSideOptions(record, usePrototypeFallback = releaseId == null || loadedRecord != null)
    val moods = BUILT_IN_SESSION_MOODS
    var customMoods by remember { mutableStateOf(emptyList<String>()) }
    var selectedSide by rememberSaveable(releaseId) { mutableStateOf("") }
    val selectedSideOption = sideOptions.firstOrNull { it.value == selectedSide } ?: sideOptions.firstOrNull()
    var selectedMood by rememberSaveable { mutableStateOf("Calm") }
    var rating by rememberSaveable { mutableStateOf(record.rating) }
    var notes by rememberSaveable { mutableStateOf("") }
    var isSaving by rememberSaveable { mutableStateOf(false) }
    var saveError by rememberSaveable { mutableStateOf<String?>(null) }
    var customMoodError by rememberSaveable { mutableStateOf<String?>(null) }
    var loadRetryKey by remember { mutableIntStateOf(0) }
    var loadError by remember(releaseId) { mutableStateOf<String?>(null) }

    LaunchedEffect(releaseId, loadRetryKey) {
        releaseId?.let { id ->
            runCatching { apiClient.getRelease(id) }
                .onSuccess {
                    loadedRecord = it
                    loadError = null
                }.onFailure { error ->
                    loadError = error.toUserMessage("Could not load record details. Using local prototype data.")
                }
        }
    }

    LaunchedEffect(sideOptions) {
        if (sideOptions.none { it.value == selectedSide }) {
            selectedSide = sideOptions.firstOrNull()?.value.orEmpty()
        }
    }

    LaunchedEffect(Unit) {
        runCatching { apiClient.getCustomMoods() }
            .onSuccess { moodsFromApi ->
                customMoods =
                    moodsFromApi
                        .filter { isValidCustomMood(it) && !isBuiltInMood(it, moods) }
                        .distinctBy { it.lowercase() }
                customMoodError = null
            }.onFailure { error ->
                customMoodError = error.toUserMessage("Custom moods could not be loaded.")
            }
    }

    fun saveSession() {
        val targetReleaseId = releaseId ?: record.releaseId
        isSaving = true
        saveError = null
        scope.launch {
            runCatching {
                apiClient.createSession(
                    releaseId = targetReleaseId,
                    side = selectedSideOption?.value?.takeIf { it.isNotBlank() },
                    rating = rating,
                    mood = selectedMood,
                    notes = notes,
                )
            }.onSuccess {
                onSave(targetReleaseId)
            }.onFailure { error ->
                saveError = error.toUserMessage("Session could not be saved. Check the form and retry.")
                isSaving = false
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
        SessionLoggingHeader(onCancel = onCancel)
        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXl),
        ) {
            SessionRecordCard(record = record)
            loadError?.let { message ->
                Text(
                    modifier =
                        Modifier
                            .clip(VinylShapes.Chip)
                            .background(VinylColors.SurfacePrimary)
                            .clickable { loadRetryKey += 1 }
                            .padding(horizontal = VinylSpacing.SpaceLg, vertical = VinylSpacing.SpaceMd),
                    text = "$message Tap to retry.",
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            SessionFieldLabel("Side Played")
            SessionSideSelector(
                selectedSide = selectedSideOption,
                sideOptions = sideOptions,
                onSideSelected = { selectedSide = it },
            )
            SessionFieldLabel("Rating")
            SessionRatingPicker(rating = rating, onRatingChange = { rating = it })
            SessionFieldLabel("Mood")
            SessionMoodGrid(
                moods = moods,
                customMoods = customMoods,
                selectedMood = selectedMood,
                onMoodSelected = { selectedMood = it },
                onSaveCustomMood = { mood ->
                    val normalizedMood = sanitizeCustomMood(mood).trim()
                    if (isExistingMood(normalizedMood, moods, customMoods)) {
                        customMoodError = "That mood already exists."
                    } else {
                        scope.launch {
                            runCatching { apiClient.createCustomMood(normalizedMood) }
                                .onSuccess { savedMood ->
                                    val cleanedMood = sanitizeCustomMood(savedMood).trim()
                                    if (isExistingMood(cleanedMood, moods, customMoods)) {
                                        customMoodError = "That mood already exists."
                                    } else {
                                        customMoods = saveCustomMood(customMoods, cleanedMood, moods)
                                        selectedMood = cleanedMood
                                        customMoodError = null
                                    }
                                }.onFailure { error ->
                                    customMoodError = error.toUserMessage("Custom mood could not be saved.")
                                }
                        }
                    }
                },
                onDeleteCustomMood = { mood ->
                    scope.launch {
                        runCatching { apiClient.deleteCustomMood(mood) }
                            .onSuccess {
                                customMoods = deleteCustomMood(customMoods, mood)
                                if (selectedMood == mood) selectedMood = "Calm"
                                customMoodError = null
                            }.onFailure { error ->
                                customMoodError = error.toUserMessage("Custom mood could not be deleted.")
                            }
                    }
                },
            )
            customMoodError?.let { message ->
                Text(
                    text = message,
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            SessionFieldLabel("Notes (Optional)")
            SessionNotesField(notes = notes, onNotesChange = { notes = it })
            saveError?.let { message ->
                Text(
                    text = message,
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Spacer(Modifier.height(VinylSpacing.SpaceLg))
        }
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(top = VinylSpacing.SpaceLg, bottom = 32.dp),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
        ) {
            SessionCancelButton(onClick = onCancel, modifier = Modifier.weight(1f))
            SessionSaveButton(
                label = if (isSaving) "Saving..." else "Save Session",
                onClick = { if (!isSaving) saveSession() },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun SessionLoggingHeader(onCancel: () -> Unit) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceXl),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CloseCircleButton(onClick = onCancel)
        Text(
            text = "Log Session",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleLarge,
        )
        Spacer(Modifier.width(40.dp))
    }
}

@Composable
private fun SessionRecordCard(record: RecordSummary) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(152.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceXl),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RecordDetailAlbumArtBlock(
                imageUrl = record.coverImageUrl,
                contentDescription = "${record.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceLg))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = record.artist,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = record.title,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = record.year.toString(),
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = "-",
                        color = VinylColors.BorderDefault,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = record.label,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun SessionFieldLabel(label: String) {
    Text(
        text = label,
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.titleMedium,
    )
}

@Composable
private fun SessionSideSelector(
    selectedSide: SessionSideOption?,
    sideOptions: List<SessionSideOption>,
    onSideSelected: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    var selectorWidth by remember { mutableStateOf(Dp.Unspecified) }
    val density = LocalDensity.current
    val sideSelectorActionLabel = if (expanded) "Close side selector" else "Open side selector"
    val anchorModifier =
        Modifier
            .fillMaxWidth()
            .onGloballyPositioned { coordinates ->
                selectorWidth = with(density) { coordinates.size.width.toDp() }
            }
    val selectorModifier =
        Modifier
            .fillMaxWidth()
            .height(60.dp)
            .clip(VinylShapes.Card)
            .background(VinylColors.SurfacePrimary)
            .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
            .clickable(
                onClickLabel = sideSelectorActionLabel,
                role = Role.Button,
                onClick = { expanded = !expanded },
            ).padding(horizontal = VinylSpacing.SpaceMd)

    Box(modifier = anchorModifier) {
        Row(
            modifier = selectorModifier,
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = selectedSide?.label.orEmpty(),
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = if (expanded) "⌄" else "<",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        if (expanded) {
            Popup(
                alignment = Alignment.TopStart,
                offset = IntOffset(x = 0, y = with(density) { 62.dp.roundToPx() }),
                onDismissRequest = { expanded = false },
                properties = PopupProperties(focusable = true),
            ) {
                Column(
                    modifier =
                        Modifier
                            .width(selectorWidth)
                            .clip(VinylShapes.Card)
                            .background(VinylColors.SurfacePrimary)
                            .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card),
                ) {
                    sideOptions.forEachIndexed { index, sideOption ->
                        val rowColor = if (index % 2 == 0) VinylColors.SurfacePrimary else VinylColors.SurfaceSecondary
                        val selectSide = {
                            onSideSelected(sideOption.value)
                            expanded = false
                        }
                        val rowModifier =
                            Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                                .background(rowColor)
                                .clickable(
                                    onClickLabel = "Select ${sideOption.label}",
                                    role = Role.Button,
                                    onClick = selectSide,
                                ).padding(horizontal = VinylSpacing.SpaceMd)

                        Row(
                            modifier = rowModifier,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = sideOption.label,
                                color =
                                    if (sideOption.value == selectedSide?.value) {
                                        VinylColors.AccentGreen
                                    } else {
                                        VinylColors.TextPrimary
                                    },
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                }
            }
        }
    }
}

internal data class SessionSideOption(
    val value: String,
    val label: String,
)

internal fun sessionSideOptions(
    record: RecordSummary,
    usePrototypeFallback: Boolean = true,
): List<SessionSideOption> =
    when {
        record.availableSideOptions.isNotEmpty() -> record.availableSideOptions.map { it.toSessionSideOption() }
        record.availableSides.isNotEmpty() -> record.availableSides.map { SessionSideOption(it, displaySessionSide(it)) }
        usePrototypeFallback -> listOf("A", "B").map { SessionSideOption(it, displaySessionSide(it)) }
        else -> emptyList()
    }

private fun ReleaseSideOption.toSessionSideOption(): SessionSideOption = SessionSideOption(value = value, label = label)

internal fun displaySessionSide(side: String): String = side.takeIf { it.isNotBlank() }?.let { "Side $it" }.orEmpty()

private fun saveCustomMood(
    currentMoods: List<String>,
    mood: String,
    builtInMoods: List<String> = BUILT_IN_SESSION_MOODS,
): List<String> {
    val normalizedMood = sanitizeCustomMood(mood).trim()
    if (!isValidCustomMood(normalizedMood) || isBuiltInMood(normalizedMood, builtInMoods)) return currentMoods
    val updated =
        (currentMoods.filterNot { it.equals(normalizedMood, ignoreCase = true) } + normalizedMood)
            .distinctBy { it.lowercase() }
    return updated
}

private fun deleteCustomMood(
    currentMoods: List<String>,
    mood: String,
): List<String> = currentMoods.filterNot { it.equals(mood, ignoreCase = true) }

private fun sanitizeCustomMood(value: String): String =
    value
        .filter { it.isLetterOrDigit() || it.isWhitespace() }
        .take(CUSTOM_MOOD_MAX_LENGTH)

private fun isValidCustomMood(value: String): Boolean = value.trim().length in CUSTOM_MOOD_MIN_LENGTH..CUSTOM_MOOD_MAX_LENGTH

internal fun isBuiltInMood(
    value: String,
    builtInMoods: List<String> = BUILT_IN_SESSION_MOODS,
): Boolean = builtInMoods.any { it.equals(value.trim(), ignoreCase = true) }

internal fun isExistingMood(
    value: String,
    builtInMoods: List<String> = BUILT_IN_SESSION_MOODS,
    customMoods: List<String> = emptyList(),
): Boolean =
    isBuiltInMood(value, builtInMoods) ||
        customMoods.any { it.equals(value.trim(), ignoreCase = true) }

@Composable
private fun SessionRatingPicker(
    rating: Int,
    onRatingChange: (Int) -> Unit,
) {
    RatingStars(
        rating = rating,
        modifier = Modifier.fillMaxWidth(),
        starSize = 44.dp,
        strokeWidth = 3.dp,
        spacing = VinylSpacing.SpaceMd,
        onRatingChange = onRatingChange,
    )
}

@Composable
private fun SessionMoodGrid(
    moods: List<String>,
    customMoods: List<String>,
    selectedMood: String,
    onMoodSelected: (String) -> Unit,
    onSaveCustomMood: (String) -> Unit,
    onDeleteCustomMood: (String) -> Unit,
) {
    var inputVisible by rememberSaveable { mutableStateOf(false) }
    var inputValue by rememberSaveable { mutableStateOf("") }
    var deleteCandidate by remember { mutableStateOf<String?>(null) }
    var popupWidth by remember { mutableStateOf(Dp.Unspecified) }
    val density = LocalDensity.current
    val inputPopupTargetOffset =
        if (WindowInsets.ime.getBottom(density) > 0) {
            with(density) { (-72).dp.roundToPx() }
        } else {
            0
        }
    val inputPopupYOffset by animateIntAsState(
        targetValue = inputPopupTargetOffset,
        label = "custom-mood-input-offset",
    )
    val sanitizedInput = sanitizeCustomMood(inputValue)
    val canSave = isValidCustomMood(sanitizedInput)

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .onGloballyPositioned { coordinates ->
                    popupWidth = with(density) { coordinates.size.width.toDp() }
                },
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
            moods.chunked(3).forEach { rowMoods ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                ) {
                    rowMoods.forEach { mood ->
                        SessionMoodChip(
                            label = mood,
                            selected = mood == selectedMood,
                            onClick = { onMoodSelected(mood) },
                        )
                    }
                }
            }
            customMoods.chunked(2).forEach { rowMoods ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                ) {
                    rowMoods.forEach { mood ->
                        SessionMoodChip(
                            label = mood,
                            selected = mood == selectedMood,
                            showDeleteIcon = true,
                            onClick = { onMoodSelected(mood) },
                            onLongClick = { deleteCandidate = mood },
                        )
                    }
                }
            }
            SessionMoodChip(
                label = "Custom",
                selected = false,
                leadingIcon = Icons.Filled.Add,
                onClick = {
                    inputValue = ""
                    inputVisible = true
                },
            )
        }
        if (inputVisible) {
            Popup(
                alignment = Alignment.TopStart,
                offset = IntOffset(x = 0, y = inputPopupYOffset),
                onDismissRequest = { inputVisible = false },
                properties = PopupProperties(focusable = true),
            ) {
                SessionCustomMoodInput(
                    value = inputValue,
                    onValueChange = { inputValue = sanitizeCustomMood(it) },
                    canSave = canSave,
                    onDismiss = { inputVisible = false },
                    onSave = {
                        if (canSave) {
                            onSaveCustomMood(sanitizedInput)
                            inputVisible = false
                            inputValue = ""
                        }
                    },
                    modifier = Modifier.sessionMoodPopupWidth(popupWidth),
                )
            }
        }
        deleteCandidate?.let { mood ->
            Popup(
                alignment = Alignment.TopStart,
                onDismissRequest = { deleteCandidate = null },
                properties = PopupProperties(focusable = true),
            ) {
                SessionDeleteMoodPopup(
                    onCancel = { deleteCandidate = null },
                    onConfirm = {
                        onDeleteCustomMood(mood)
                        deleteCandidate = null
                    },
                    modifier = Modifier.sessionMoodPopupWidth(popupWidth),
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun SessionMoodChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    leadingIcon: androidx.compose.ui.graphics.vector.ImageVector? = null,
    showDeleteIcon: Boolean = false,
    onLongClick: (() -> Unit)? = null,
) {
    val fill = if (selected) VinylColors.GreenTint20 else VinylColors.SurfacePrimary
    val border = if (selected) VinylColors.AccentGreen else VinylColors.BorderDefault
    val textColor = if (selected) VinylColors.AccentGreen else VinylColors.TextSecondary

    Box(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(fill)
                .border(1.dp, border, VinylShapes.Chip)
                .combinedClickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onLongClick = onLongClick,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceLg, vertical = VinylSpacing.SpaceSm),
        contentAlignment = Alignment.Center,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            leadingIcon?.let { icon ->
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = textColor,
                    modifier = Modifier.size(16.dp),
                )
            }
            if (showDeleteIcon) {
                Icon(
                    imageVector = Icons.Filled.Close,
                    contentDescription = null,
                    tint = textColor,
                    modifier = Modifier.size(16.dp),
                )
            }
            Text(
                text = label,
                color = textColor,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

private fun Modifier.sessionMoodPopupWidth(width: Dp): Modifier =
    if (width == Dp.Unspecified) {
        fillMaxWidth()
    } else {
        this.width(width)
    }

@Composable
private fun SessionCustomMoodInput(
    value: String,
    onValueChange: (String) -> Unit,
    canSave: Boolean,
    onDismiss: () -> Unit,
    onSave: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier =
            modifier
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
            modifier = Modifier.weight(1f),
            singleLine = true,
            textStyle =
                MaterialTheme.typography.bodyMedium.copy(
                    color = VinylColors.TextPrimary,
                ),
            cursorBrush = SolidColor(VinylColors.AccentGreen),
            decorationBox = { innerTextField ->
                if (value.isBlank()) {
                    Text(
                        text = "Custom mood",
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
                        onClickLabel = if (canSave) "Save custom mood" else "Dismiss custom mood input",
                        role = Role.Button,
                        onClick = { if (canSave) onSave() else onDismiss() },
                    ).padding(VinylSpacing.SpaceSm),
            imageVector = if (canSave) Icons.Filled.Check else Icons.Filled.Close,
            contentDescription = null,
            tint = if (canSave) VinylColors.AccentGreen else VinylColors.TextSecondary,
        )
    }
}

@Composable
private fun SessionDeleteMoodPopup(
    onCancel: () -> Unit,
    onConfirm: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier =
            modifier
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceXl),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
    ) {
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = "Do you want to delete this mood?",
            color = VinylColors.TextPrimary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyLarge,
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            SessionMoodPopupAction(
                label = "Cancel",
                color = VinylColors.TextSecondary,
                onClick = onCancel,
                modifier = Modifier.weight(1f),
            )
            SessionMoodPopupAction(
                label = "Confirm",
                color = VinylColors.AccentGreen,
                onClick = onConfirm,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun SessionMoodPopupAction(
    label: String,
    color: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Text(
        modifier =
            modifier
                .clip(VinylShapes.Chip)
                .background(VinylColors.SurfaceSecondary)
                .clickable(onClickLabel = label, role = Role.Button, onClick = onClick)
                .padding(vertical = VinylSpacing.SpaceMd),
        text = label,
        color = color,
        textAlign = TextAlign.Center,
        style = MaterialTheme.typography.labelLarge,
    )
}

@Composable
private fun SessionNotesField(
    notes: String,
    onNotesChange: (String) -> Unit,
) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(228.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        BasicTextField(
            value = notes,
            onValueChange = onNotesChange,
            modifier = Modifier.fillMaxSize(),
            textStyle =
                MaterialTheme.typography.bodyMedium.copy(
                    color = VinylColors.TextPrimary,
                ),
            cursorBrush = SolidColor(VinylColors.AccentGreen),
            decorationBox = { innerTextField ->
                if (notes.isEmpty()) {
                    Text(
                        text = "Add your listening notes...",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                innerTextField()
            },
        )
    }
}

@Composable
private fun SessionCancelButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(66.dp)
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .clickable(
                    onClickLabel = "Cancel",
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "Cancel",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun SessionSaveButton(
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
                .height(66.dp)
                .clip(VinylShapes.Card)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Card)
                .clickable(
                    onClickLabel = "Save session",
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
