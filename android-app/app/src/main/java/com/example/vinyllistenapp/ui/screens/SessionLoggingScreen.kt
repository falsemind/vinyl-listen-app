package com.example.vinyllistenapp.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.animateIntAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseSideOption
import com.example.vinyllistenapp.domain.ReleaseTrack
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
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
    val trackOptions = sessionTrackOptions(record, selectedSideOption)
    var selectedTrackPositions by rememberSaveable(releaseId) { mutableStateOf(emptyList<String>()) }
    var selectedMood by rememberSaveable { mutableStateOf("Calm") }
    var rating by rememberSaveable { mutableStateOf(record.rating) }
    var notes by rememberSaveable { mutableStateOf("") }
    var isSaving by rememberSaveable { mutableStateOf(false) }
    var saveError by rememberSaveable { mutableStateOf<String?>(null) }
    var customMoodValidationError by rememberSaveable { mutableStateOf<String?>(null) }
    var customMoodServerError by rememberSaveable { mutableStateOf<String?>(null) }
    var loadRetryKey by remember { mutableIntStateOf(0) }
    var customMoodRetryKey by remember { mutableIntStateOf(0) }
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
            selectedTrackPositions = emptyList()
        }
    }

    LaunchedEffect(trackOptions) {
        val availablePositions = trackOptions.map { it.position }.toSet()
        selectedTrackPositions = selectedTrackPositions.filter { it in availablePositions }
    }

    LaunchedEffect(customMoodRetryKey) {
        runCatching { apiClient.getCustomMoods() }
            .onSuccess { moodsFromApi ->
                customMoods =
                    moodsFromApi
                        .filter { isValidCustomMood(it) && !isBuiltInMood(it, moods) }
                        .distinctBy { it.lowercase() }
                customMoodServerError = null
            }.onFailure { error ->
                customMoodServerError = error.toUserMessage("Custom moods could not be loaded.")
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
                    trackPositions = selectedTrackPositions,
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

    fun retryServerError() {
        when {
            saveError != null -> saveSession()
            loadError != null -> loadRetryKey += 1
            customMoodServerError != null -> customMoodRetryKey += 1
        }
    }

    val serverError = saveError ?: loadError ?: customMoodServerError

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd),
    ) {
        SessionLoggingHeader(onCancel = onCancel)
        serverError?.let { message ->
            ErrorRetryCard(message = message, onRetry = ::retryServerError)
            Spacer(Modifier.height(VinylSpacing.SpaceXl))
        }
        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXl),
        ) {
            SessionRecordCard(record = record)
            SessionFieldLabel("Side Played")
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                SessionSideSelector(
                    selectedSide = selectedSideOption,
                    sideOptions = sideOptions,
                    onSideSelected = {
                        selectedSide = it
                        selectedTrackPositions = emptyList()
                    },
                )
                if (trackOptions.isNotEmpty()) {
                    SessionTrackSelector(
                        trackOptions = trackOptions,
                        selectedPositions = selectedTrackPositions,
                        onSelectionChange = { selectedTrackPositions = it },
                    )
                }
            }
            SessionFieldLabel("Rating")
            SessionRatingPicker(rating = rating, onRatingChange = { rating = it })
            SessionFieldLabel("Mood")
            SessionMoodGrid(
                moods = moods,
                customMoods = customMoods,
                selectedMood = selectedMood,
                onMoodSelected = {
                    selectedMood = it
                    customMoodValidationError = null
                },
                onSaveCustomMood = { mood ->
                    val normalizedMood = sanitizeCustomMood(mood).trim()
                    if (isExistingMood(normalizedMood, moods, customMoods)) {
                        customMoodValidationError = "That mood already exists."
                    } else {
                        scope.launch {
                            runCatching { apiClient.createCustomMood(normalizedMood) }
                                .onSuccess { savedMood ->
                                    val cleanedMood = sanitizeCustomMood(savedMood).trim()
                                    if (isExistingMood(cleanedMood, moods, customMoods)) {
                                        customMoodValidationError = "That mood already exists."
                                    } else {
                                        customMoods = saveCustomMood(customMoods, cleanedMood, moods)
                                        selectedMood = cleanedMood
                                        customMoodValidationError = null
                                        customMoodServerError = null
                                    }
                                }.onFailure { error ->
                                    customMoodValidationError = null
                                    customMoodServerError = error.toUserMessage("Custom mood could not be saved.")
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
                                customMoodValidationError = null
                                customMoodServerError = null
                            }.onFailure { error ->
                                customMoodServerError = error.toUserMessage("Custom mood could not be deleted.")
                            }
                    }
                },
            )
            customMoodValidationError?.let { message ->
                Text(
                    text = message,
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            SessionFieldLabel("Notes (Optional)")
            SessionNotesField(notes = notes, onNotesChange = { notes = it })
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
fun EditSessionScreen(
    sessionId: String?,
    apiClient: VinylApiClient,
    onSave: (String) -> Unit,
    onCancel: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var loadedSession by remember(sessionId) { mutableStateOf<ListeningSession?>(null) }
    var loadedRecord by remember(sessionId) { mutableStateOf<RecordSummary?>(null) }
    val record = loadedRecord ?: MockVinylData.record(loadedSession?.releaseId)
    val sideOptions = sessionSideOptions(record, usePrototypeFallback = loadedRecord != null)
    val moods = BUILT_IN_SESSION_MOODS
    var customMoods by remember { mutableStateOf(emptyList<String>()) }
    var selectedSide by rememberSaveable(sessionId) { mutableStateOf("") }
    val selectedSideOption = sideOptions.firstOrNull { it.value == selectedSide } ?: sideOptions.firstOrNull()
    val trackOptions = sessionTrackOptions(record, selectedSideOption)
    var selectedTrackPositions by rememberSaveable(sessionId) { mutableStateOf(emptyList<String>()) }
    var selectedMood by rememberSaveable(sessionId) { mutableStateOf("Calm") }
    var rating by rememberSaveable(sessionId) { mutableStateOf(0) }
    var notes by rememberSaveable(sessionId) { mutableStateOf("") }
    var isLoading by rememberSaveable(sessionId) { mutableStateOf(true) }
    var isSaving by rememberSaveable(sessionId) { mutableStateOf(false) }
    var saveError by rememberSaveable(sessionId) { mutableStateOf<String?>(null) }
    var customMoodValidationError by rememberSaveable { mutableStateOf<String?>(null) }
    var customMoodServerError by rememberSaveable { mutableStateOf<String?>(null) }
    var loadRetryKey by remember { mutableIntStateOf(0) }
    var customMoodRetryKey by remember { mutableIntStateOf(0) }
    var loadError by remember(sessionId) { mutableStateOf<String?>(null) }

    LaunchedEffect(sessionId, loadRetryKey) {
        val targetSessionId = sessionId?.takeIf { it.isNotBlank() }
        if (targetSessionId == null) {
            isLoading = false
            loadError = "Session could not be opened."
            return@LaunchedEffect
        }
        isLoading = true
        runCatching {
            val session = apiClient.getSession(targetSessionId)
            session to apiClient.getRelease(session.releaseId)
        }.onSuccess { (session, release) ->
            loadedSession = session
            loadedRecord = release
            selectedSide = session.side.orEmpty()
            selectedTrackPositions = session.tracks.map { it.position }
            selectedMood = session.mood.takeIf { it.isNotBlank() && it != "Unspecified" } ?: "Calm"
            rating = session.rating
            notes = session.notes.orEmpty()
            loadError = null
        }.onFailure { error ->
            loadError = error.toUserMessage("Could not load session.")
        }
        isLoading = false
    }

    LaunchedEffect(sideOptions) {
        if (sideOptions.isNotEmpty() && sideOptions.none { it.value == selectedSide }) {
            selectedSide = sideOptions.first().value
            selectedTrackPositions = emptyList()
        }
    }

    LaunchedEffect(trackOptions) {
        val availablePositions = trackOptions.map { it.position }.toSet()
        selectedTrackPositions = selectedTrackPositions.filter { it in availablePositions }
    }

    LaunchedEffect(customMoodRetryKey) {
        runCatching { apiClient.getCustomMoods() }
            .onSuccess { moodsFromApi ->
                customMoods =
                    moodsFromApi
                        .filter { isValidCustomMood(it) && !isBuiltInMood(it, moods) }
                        .distinctBy { it.lowercase() }
                customMoodServerError = null
            }.onFailure { error ->
                customMoodServerError = error.toUserMessage("Custom moods could not be loaded.")
            }
    }

    fun saveSession() {
        val session = loadedSession ?: return
        isSaving = true
        saveError = null
        scope.launch {
            runCatching {
                apiClient.updateSession(
                    sessionId = session.sessionId ?: sessionId.orEmpty(),
                    side = selectedSideOption?.value?.takeIf { it.isNotBlank() },
                    trackPositions = selectedTrackPositions,
                    rating = rating.takeIf { it > 0 },
                    mood = selectedMood,
                    notes = notes,
                )
            }.onSuccess { updatedSession ->
                onSave(updatedSession.releaseId.ifBlank { session.releaseId })
            }.onFailure { error ->
                saveError = error.toUserMessage("Session could not be updated. Check the form and retry.")
                isSaving = false
            }
        }
    }

    fun retryServerError() {
        when {
            saveError != null -> saveSession()
            loadError != null -> loadRetryKey += 1
            customMoodServerError != null -> customMoodRetryKey += 1
        }
    }

    val serverError = saveError ?: loadError ?: customMoodServerError

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd),
    ) {
        SessionLoggingHeader(title = "Edit Session", onCancel = onCancel)
        serverError?.let { message ->
            ErrorRetryCard(message = message, onRetry = ::retryServerError)
            Spacer(Modifier.height(VinylSpacing.SpaceXl))
        }
        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXl),
        ) {
            SessionRecordCard(record = record)
            SessionFieldLabel("Side Played")
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                SessionSideSelector(
                    selectedSide = selectedSideOption,
                    sideOptions = sideOptions,
                    onSideSelected = {
                        selectedSide = it
                        selectedTrackPositions = emptyList()
                    },
                )
                if (trackOptions.isNotEmpty()) {
                    SessionTrackSelector(
                        trackOptions = trackOptions,
                        selectedPositions = selectedTrackPositions,
                        onSelectionChange = { selectedTrackPositions = it },
                    )
                }
            }
            SessionFieldLabel("Rating")
            SessionRatingPicker(rating = rating, onRatingChange = { rating = it })
            SessionFieldLabel("Mood")
            SessionMoodGrid(
                moods = moods,
                customMoods = customMoods,
                selectedMood = selectedMood,
                onMoodSelected = {
                    selectedMood = it
                    customMoodValidationError = null
                },
                onSaveCustomMood = { mood ->
                    val normalizedMood = sanitizeCustomMood(mood).trim()
                    if (isExistingMood(normalizedMood, moods, customMoods)) {
                        customMoodValidationError = "That mood already exists."
                    } else {
                        scope.launch {
                            runCatching { apiClient.createCustomMood(normalizedMood) }
                                .onSuccess { savedMood ->
                                    val cleanedMood = sanitizeCustomMood(savedMood).trim()
                                    if (isExistingMood(cleanedMood, moods, customMoods)) {
                                        customMoodValidationError = "That mood already exists."
                                    } else {
                                        customMoods = saveCustomMood(customMoods, cleanedMood, moods)
                                        selectedMood = cleanedMood
                                        customMoodValidationError = null
                                        customMoodServerError = null
                                    }
                                }.onFailure { error ->
                                    customMoodValidationError = null
                                    customMoodServerError = error.toUserMessage("Custom mood could not be saved.")
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
                                customMoodValidationError = null
                                customMoodServerError = null
                            }.onFailure { error ->
                                customMoodServerError = error.toUserMessage("Custom mood could not be deleted.")
                            }
                    }
                },
            )
            customMoodValidationError?.let { message ->
                Text(
                    text = message,
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            SessionFieldLabel("Notes (Optional)")
            SessionNotesField(notes = notes, onNotesChange = { notes = it })
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
                label =
                    when {
                        isLoading -> "Loading..."
                        isSaving -> "Saving..."
                        else -> "Save Changes"
                    },
                onClick = { if (!isSaving && !isLoading) saveSession() },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun SessionLoggingHeader(
    title: String = "Log Session",
    onCancel: () -> Unit,
) {
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
            text = title,
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
    val arrowRotation by animateFloatAsState(
        targetValue = if (expanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "Side selector arrow rotation",
    )
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
            Icon(
                imageVector = Icons.Filled.KeyboardArrowUp,
                contentDescription = null,
                tint = VinylColors.TextSecondary,
                modifier =
                    Modifier
                        .size(28.dp)
                        .graphicsLayer { rotationZ = arrowRotation },
            )
        }
        if (expanded) {
            var dropdownVisible by remember { mutableStateOf(false) }
            LaunchedEffect(Unit) {
                dropdownVisible = true
            }
            val dropdownAlpha by animateFloatAsState(
                targetValue = if (dropdownVisible) 1f else 0f,
                animationSpec = tween(durationMillis = 140),
                label = "Side dropdown fade",
            )
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
                            .graphicsLayer { alpha = dropdownAlpha }
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

@Composable
private fun SessionTrackSelector(
    trackOptions: List<SessionTrackOption>,
    selectedPositions: List<String>,
    onSelectionChange: (List<String>) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    var selectorWidth by remember { mutableStateOf(Dp.Unspecified) }
    val density = LocalDensity.current
    val selectedPositionSet = selectedPositions.toSet()
    val allPositions = trackOptions.map { it.position }
    val allTracksSelected = trackOptions.isNotEmpty() && selectedPositionSet.containsAll(allPositions)
    val actionLabel = if (expanded) "Close track selector" else "Open track selector"
    val arrowRotation by animateFloatAsState(
        targetValue = if (expanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "Track selector arrow rotation",
    )
    val anchorModifier =
        Modifier
            .fillMaxWidth()
            .onGloballyPositioned { coordinates ->
                selectorWidth = with(density) { coordinates.size.width.toDp() }
            }

    Box(modifier = anchorModifier) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                    .clickable(
                        role = Role.Button,
                        onClickLabel = actionLabel,
                    ) { expanded = !expanded }
                    .padding(horizontal = VinylSpacing.SpaceMd)
                    .height(56.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            TrackSelectionSummary(
                selectedCount = selectedPositionSet.size,
                totalCount = trackOptions.size,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.Filled.KeyboardArrowUp,
                contentDescription = null,
                tint = VinylColors.TextSecondary,
                modifier =
                    Modifier
                        .size(28.dp)
                        .graphicsLayer { rotationZ = arrowRotation },
            )
        }
        if (expanded) {
            var dropdownVisible by remember { mutableStateOf(false) }
            LaunchedEffect(Unit) {
                dropdownVisible = true
            }
            val dropdownAlpha by animateFloatAsState(
                targetValue = if (dropdownVisible) 1f else 0f,
                animationSpec = tween(durationMillis = 140),
                label = "Track dropdown fade",
            )
            Popup(
                alignment = Alignment.TopStart,
                offset = IntOffset(x = 0, y = with(density) { 62.dp.roundToPx() }),
                onDismissRequest = { expanded = false },
                properties = PopupProperties(focusable = true),
            ) {
                Column(
                    modifier =
                        Modifier
                            .width(selectorWidth.takeIf { it != Dp.Unspecified } ?: 240.dp)
                            .heightIn(max = 320.dp)
                            .graphicsLayer { alpha = dropdownAlpha }
                            .clip(VinylShapes.Card)
                            .background(VinylColors.SurfacePrimary)
                            .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                            .verticalScroll(rememberScrollState()),
                ) {
                    TrackSelectorRow(
                        label = "Played all tracks",
                        selected = allTracksSelected,
                        onClick = {
                            onSelectionChange(if (allTracksSelected) emptyList() else allPositions)
                        },
                    )
                    trackOptions.forEachIndexed { index, trackOption ->
                        TrackSelectorRow(
                            label = trackOption.label,
                            selected = trackOption.position in selectedPositionSet,
                            alternate = index % 2 == 0,
                            onClick = {
                                val nextSelection =
                                    if (trackOption.position in selectedPositionSet) {
                                        selectedPositions.filterNot { it == trackOption.position }
                                    } else {
                                        (selectedPositions + trackOption.position).sortedBy { position ->
                                            allPositions.indexOf(position).takeIf { it >= 0 } ?: Int.MAX_VALUE
                                        }
                                    }
                                onSelectionChange(nextSelection)
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TrackSelectionSummary(
    selectedCount: Int,
    totalCount: Int,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when {
            selectedCount == 0 -> {
                Text(
                    text = "Track(s) played",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            selectedCount == totalCount -> {
                Text(
                    text = "All",
                    color = VinylColors.AccentGreen,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = " tracks played",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            else -> {
                Text(
                    text = selectedCount.toString(),
                    color = VinylColors.AccentGreen,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = if (selectedCount == 1) " track played" else " tracks played",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun TrackSelectorRow(
    label: String,
    selected: Boolean,
    alternate: Boolean = false,
    onClick: () -> Unit,
) {
    val rowColor = if (alternate) VinylColors.SurfacePrimary else VinylColors.SurfaceSecondary
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(rowColor)
                .clickable(
                    role = Role.Checkbox,
                    onClickLabel = label,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceSm),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Box(
            modifier =
                Modifier
                    .size(20.dp)
                    .clip(CircleShape)
                    .background(if (selected) VinylColors.AccentGreen else Color.Transparent)
                    .border(
                        width = 1.dp,
                        color = if (selected) VinylColors.AccentGreen else VinylColors.BorderDefault,
                        shape = CircleShape,
                    ),
            contentAlignment = Alignment.Center,
        ) {
            if (selected) {
                Icon(
                    imageVector = Icons.Filled.Check,
                    contentDescription = null,
                    tint = VinylColors.SurfacePrimary,
                    modifier = Modifier.size(14.dp),
                )
            }
        }
        Text(
            text = label,
            color = if (selected) VinylColors.AccentGreen else VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

internal data class SessionSideOption(
    val value: String,
    val label: String,
)

internal data class SessionTrackOption(
    val position: String,
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

internal fun sessionTrackOptions(
    record: RecordSummary,
    selectedSide: SessionSideOption?,
): List<SessionTrackOption> {
    val selectedSideKey =
        selectedSide
            ?.value
            ?.substringAfterLast(":")
            ?.takeIf { it.isNotBlank() }
            ?.uppercase()
            ?: return emptyList()
    return record.tracklist
        .filter { track -> track.sidePrefix() == selectedSideKey }
        .map { track ->
            SessionTrackOption(
                position = track.position,
                label = displaySessionTrack(track),
            )
        }
}

internal fun displaySessionTrack(track: ReleaseTrack): String =
    buildString {
        append(track.position)
        append(": ")
        append(track.title)
        track.duration?.takeIf { it.isNotBlank() }?.let { duration ->
            append(" ")
            append(duration)
        }
    }

private fun ReleaseTrack.sidePrefix(): String? {
    val letters = position.trim().uppercase().takeWhile { it.isLetter() }
    return letters.ifBlank { null }
}

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
            WrappingChipRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalSpacing = VinylSpacing.SpaceSm,
                verticalSpacing = VinylSpacing.SpaceMd,
            ) {
                moods.forEach { mood ->
                    SessionMoodChip(
                        label = mood,
                        selected = mood == selectedMood,
                        onClick = { onMoodSelected(mood) },
                    )
                }
                customMoods.forEach { mood ->
                    SessionMoodChip(
                        label = mood,
                        selected = mood == selectedMood,
                        showDeleteIcon = true,
                        onClick = { onMoodSelected(mood) },
                        onLongClick = { deleteCandidate = mood },
                    )
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
            AlertDialog(
                onDismissRequest = { deleteCandidate = null },
                title = { Text("Delete custom mood?") },
                text = { Text("This removes \"$mood\" from your custom mood list.") },
                confirmButton = {
                    TextButton(
                        onClick = {
                            onDeleteCustomMood(mood)
                            deleteCandidate = null
                        },
                    ) {
                        Text("Delete")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { deleteCandidate = null }) {
                        Text("Cancel")
                    }
                },
                containerColor = VinylColors.SurfacePrimary,
                titleContentColor = VinylColors.TextPrimary,
                textContentColor = VinylColors.TextSecondary,
            )
        }
    }
}

@Composable
private fun WrappingChipRow(
    modifier: Modifier = Modifier,
    horizontalSpacing: Dp,
    verticalSpacing: Dp,
    content: @Composable () -> Unit,
) {
    val density = LocalDensity.current
    val horizontalGap = with(density) { horizontalSpacing.roundToPx() }
    val verticalGap = with(density) { verticalSpacing.roundToPx() }

    Layout(
        modifier = modifier,
        content = content,
    ) { measurables, constraints ->
        val placeables = measurables.map { it.measure(constraints.copy(minWidth = 0)) }
        val positions = mutableListOf<IntOffset>()
        val maxWidth = constraints.maxWidth
        var rowWidth = 0
        var rowHeight = 0
        var layoutWidth = 0
        var layoutHeight = 0

        placeables.forEach { placeable ->
            val nextWidth =
                if (rowWidth == 0) {
                    placeable.width
                } else {
                    rowWidth + horizontalGap + placeable.width
                }
            if (rowWidth > 0 && nextWidth > maxWidth) {
                layoutHeight += rowHeight + verticalGap
                rowWidth = 0
                rowHeight = 0
            }

            val x = if (rowWidth == 0) 0 else rowWidth + horizontalGap
            positions += IntOffset(x, layoutHeight)
            rowWidth = x + placeable.width
            rowHeight = maxOf(rowHeight, placeable.height)
            layoutWidth = maxOf(layoutWidth, rowWidth)
        }

        layoutHeight += rowHeight
        layout(
            width = layoutWidth.coerceIn(constraints.minWidth, constraints.maxWidth),
            height = layoutHeight.coerceIn(constraints.minHeight, constraints.maxHeight),
        ) {
            placeables.forEachIndexed { index, placeable ->
                val position = positions[index]
                placeable.placeRelative(position.x, position.y)
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
