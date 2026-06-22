package com.example.vinyllistenapp.ui.screens

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.data.manual.ManualReleaseRepository
import com.example.vinyllistenapp.domain.ManualReleaseCoverValidationState
import com.example.vinyllistenapp.domain.ManualReleaseDraft
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.example.vinyllistenapp.domain.ManualReleaseFormState
import com.example.vinyllistenapp.domain.ManualReleaseFormat
import com.example.vinyllistenapp.domain.ManualReleaseLimits
import com.example.vinyllistenapp.domain.ManualReleasePrimaryAction
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditInput
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditRole
import com.example.vinyllistenapp.domain.ManualReleaseTrackInput
import com.example.vinyllistenapp.domain.ManualReleaseVinylSize
import com.example.vinyllistenapp.domain.ManualReleaseVinylSpeed
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.CircleIconButton
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

private val MANUAL_GENRES = listOf("Electronic", "Rock", "Jazz", "Hip Hop", "Pop", "Other")
private val ELECTRONIC_STYLES = listOf("Techno", "House", "Ambient", "Electro", "Drum & Bass", "Other")
private const val MAX_EMPTY_TRACK_FORMS = 2

private data class ManualReleaseFormUiState(
    val formState: ManualReleaseFormState = ManualReleaseFormState(),
    val initialFormState: ManualReleaseFormState = ManualReleaseFormState(),
    val activeDraftId: String? = null,
    val coverPreviewImageUrl: String? = null,
    val isLoading: Boolean = false,
    val isSaving: Boolean = false,
    val loadError: String? = null,
    val saveError: String? = null,
)

private sealed class ManualFormSaveOutcome {
    data object Draft : ManualFormSaveOutcome()

    data class Release(
        val releaseId: String,
    ) : ManualFormSaveOutcome()
}

private enum class ManualFormSaveTarget {
    Draft,
    Collection,
}

private data class SelectedCoverMetadata(
    val contentType: String?,
    val sizeBytes: Int?,
    val widthPx: Int?,
    val heightPx: Int?,
)

@Composable
fun ManualReleaseFormScreen(
    apiClient: VinylApiClient,
    draftId: String?,
    onCancel: () -> Unit,
    onDraftSaved: () -> Unit,
    onReleaseSaved: (String) -> Unit,
) {
    val repository = remember(apiClient) { ManualReleaseRepository(apiClient) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var retryKey by remember { mutableIntStateOf(0) }
    var showCancelConfirmation by remember { mutableStateOf(false) }
    var showSaveAsDialog by remember { mutableStateOf(false) }
    var state by remember(draftId) {
        mutableStateOf(
            ManualReleaseFormUiState(
                activeDraftId = draftId,
                isLoading = !draftId.isNullOrBlank(),
            ),
        )
    }
    val coverPicker =
        rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            uri ?: return@rememberLauncherForActivityResult
            val metadata = context.readSelectedCoverMetadata(uri)
            state =
                state.copy(
                    formState =
                        state.formState.copy(
                            coverUri = uri.toString(),
                            coverContentType = metadata.contentType,
                            coverSizeBytes = metadata.sizeBytes,
                            coverWidthPx = metadata.widthPx,
                            coverHeightPx = metadata.heightPx,
                            dirtyFields = state.formState.dirtyFields + "cover",
                            fieldErrors = emptyMap(),
                        ),
                    saveError = null,
                )
        }

    fun updateForm(
        dirtyField: String,
        transform: (ManualReleaseFormData) -> ManualReleaseFormData,
    ) {
        state =
            state.copy(
                formState =
                    state.formState.copy(
                        formData = transform(state.formState.formData),
                        dirtyFields = state.formState.dirtyFields + dirtyField,
                        fieldErrors = emptyMap(),
                    ),
                saveError = null,
            )
    }

    fun requestCancel() {
        if (state.hasUnsavedChanges()) {
            showCancelConfirmation = true
        } else {
            onCancel()
        }
    }

    fun saveForm(target: ManualFormSaveTarget) {
        val action = state.formState.primaryAction
        if (state.isSaving || action == ManualReleasePrimaryAction.DisabledSave) return
        val coverError = state.formState.selectedCoverError()
        if (coverError != null) {
            state =
                state.copy(
                    formState = state.formState.copy(fieldErrors = state.formState.fieldErrors + ("cover" to coverError)),
                    saveError = coverError,
                )
            return
        }
        scope.launch {
            state = state.copy(isSaving = true, saveError = null)
            val submitState = state.formState.copy(formData = state.formState.formData.normalizedForManualSubmit())
            var nextActiveDraftId = state.activeDraftId
            runCatching {
                when (target) {
                    ManualFormSaveTarget.Draft -> {
                        val draft =
                            if (nextActiveDraftId.isNullOrBlank()) {
                                repository.createDraft(submitState)
                            } else {
                                repository.updateDraft(nextActiveDraftId, submitState)
                            }
                        nextActiveDraftId = draft.id
                        uploadSelectedCoverIfNeeded(context, repository, draft.id, submitState)
                        ManualFormSaveOutcome.Draft
                    }

                    ManualFormSaveTarget.Collection -> {
                        val release =
                            if (submitState.coverUri != null || !nextActiveDraftId.isNullOrBlank()) {
                                val draft =
                                    if (nextActiveDraftId.isNullOrBlank()) {
                                        repository.createDraft(submitState)
                                    } else {
                                        repository.updateDraft(nextActiveDraftId, submitState)
                                    }
                                nextActiveDraftId = draft.id
                                uploadSelectedCoverIfNeeded(context, repository, draft.id, submitState)
                                repository.saveDraftAsRelease(draft.id)
                            } else {
                                repository.saveRelease(submitState.formData)
                            }
                        ManualFormSaveOutcome.Release(release.id)
                    }
                }
            }.onSuccess { outcome ->
                state = state.copy(activeDraftId = nextActiveDraftId, isSaving = false)
                when (outcome) {
                    ManualFormSaveOutcome.Draft -> onDraftSaved()
                    is ManualFormSaveOutcome.Release -> onReleaseSaved(outcome.releaseId)
                }
            }.onFailure { failure ->
                val apiError = failure as? ApiException
                state =
                    state.copy(
                        activeDraftId = nextActiveDraftId,
                        formState = submitState.copy(fieldErrors = apiError?.fieldErrors.orEmpty()),
                        isSaving = false,
                        saveError = failure.toUserMessage("Manual release could not be saved."),
                    )
            }
        }
    }

    fun clearSelectedCover() {
        state =
            state.copy(
                formState =
                    state.formState.copy(
                        coverUri = null,
                        coverContentType = state.initialFormState.coverContentType,
                        coverSizeBytes = state.initialFormState.coverSizeBytes,
                        coverWidthPx = null,
                        coverHeightPx = null,
                        dirtyFields = state.formState.dirtyFields + "cover",
                        fieldErrors = emptyMap(),
                    ),
                saveError = null,
            )
    }

    LaunchedEffect(repository, draftId, retryKey) {
        if (draftId.isNullOrBlank()) {
            state = ManualReleaseFormUiState()
            return@LaunchedEffect
        }
        state = state.copy(isLoading = true, loadError = null)
        runCatching { repository.getDraft(draftId) }
            .onSuccess { draft ->
                val loadedState = draft.toFormState()
                state =
                    ManualReleaseFormUiState(
                        formState = loadedState,
                        initialFormState = loadedState,
                        activeDraftId = draft.id,
                        coverPreviewImageUrl = draft.coverImageUrl ?: draft.coverThumbnailUrl,
                    )
            }.onFailure { failure ->
                state =
                    state.copy(
                        isLoading = false,
                        loadError = failure.toUserMessage("Could not load manual release draft."),
                    )
            }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        topBar = {
            ManualReleaseFormTopBar(
                title = if (!draftId.isNullOrBlank()) "Edit Draft" else "Add Release",
                onClose = ::requestCancel,
            )
        },
        bottomBar = {
            ManualReleaseFormBottomActions(
                primaryAction = state.formState.primaryAction,
                isSaving = state.isSaving,
                isLoading = state.isLoading,
                onCancel = ::requestCancel,
                onSave = {
                    when (state.formState.primaryAction) {
                        ManualReleasePrimaryAction.SaveRelease -> showSaveAsDialog = true
                        ManualReleasePrimaryAction.SaveDraft -> saveForm(ManualFormSaveTarget.Draft)
                        ManualReleasePrimaryAction.DisabledSave -> Unit
                    }
                },
            )
        },
    ) { innerPadding ->
        ManualReleaseFormContent(
            state = state,
            isEditingDraft = !draftId.isNullOrBlank(),
            innerPadding = innerPadding,
            onRetry = { retryKey += 1 },
            onUpdateForm = ::updateForm,
            onSelectCover = { coverPicker.launch("image/*") },
            onClearSelectedCover = ::clearSelectedCover,
        )
    }

    if (showCancelConfirmation) {
        AlertDialog(
            onDismissRequest = { showCancelConfirmation = false },
            title = { Text("Discard changes?") },
            text = { Text("You have unsaved manual release changes.") },
            confirmButton = {
                TextButton(onClick = onCancel) {
                    Text("Discard")
                }
            },
            dismissButton = {
                TextButton(onClick = { showCancelConfirmation = false }) {
                    Text("Keep Editing")
                }
            },
        )
    }

    if (showSaveAsDialog) {
        ManualSaveAsDialog(
            isSaving = state.isSaving,
            onDismiss = { showSaveAsDialog = false },
            onSaveDraft = {
                showSaveAsDialog = false
                saveForm(ManualFormSaveTarget.Draft)
            },
            onSaveToCollection = {
                showSaveAsDialog = false
                saveForm(ManualFormSaveTarget.Collection)
            },
        )
    }
}

@Composable
private fun ManualReleaseFormTopBar(
    title: String,
    onClose: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd)
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceLg),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CloseCircleButton(onClick = onClose, contentDescription = "Close Add Release")
        Text(
            text = title,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleLarge,
        )
        Box(Modifier.size(40.dp))
    }
}

@Composable
private fun ManualSaveAsDialog(
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onSaveDraft: () -> Unit,
    onSaveToCollection: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { if (!isSaving) onDismiss() },
        title = { Text("Save as") },
        confirmButton = {
            TextButton(
                enabled = !isSaving,
                onClick = onSaveToCollection,
            ) {
                Text("To collection")
            }
        },
        dismissButton = {
            TextButton(
                enabled = !isSaving,
                onClick = onSaveDraft,
            ) {
                Text("Draft")
            }
        },
    )
}

@Composable
private fun ManualReleaseFormContent(
    state: ManualReleaseFormUiState,
    isEditingDraft: Boolean,
    innerPadding: PaddingValues,
    onRetry: () -> Unit,
    onUpdateForm: (String, (ManualReleaseFormData) -> ManualReleaseFormData) -> Unit,
    onSelectCover: () -> Unit,
    onClearSelectedCover: () -> Unit,
) {
    val scrollState = rememberScrollState()
    ScreenContent(
        title = null,
        subtitle = "Enter the core release details, format, and tracklist.",
        innerPadding = innerPadding,
        topPadding = 0.dp,
        scrollState = scrollState,
    ) {
        when {
            state.isLoading -> ManualFormLoadingCard()
            state.loadError != null -> ErrorRetryCard(message = state.loadError, onRetry = onRetry)
            else -> {
                state.saveError?.let { message ->
                    ManualSaveErrorCard(message)
                }
                ManualReleaseIdentitySection(state.formState, onUpdateForm)
                ManualReleaseFormatSection(state.formState, onUpdateForm)
                ManualReleaseCoverSection(
                    formState = state.formState,
                    previewImageUrl = state.formState.coverUri ?: state.coverPreviewImageUrl,
                    onSelectCover = onSelectCover,
                    onClearSelectedCover = onClearSelectedCover,
                )
                ManualReleaseTracklistSection(state.formState, onUpdateForm)
            }
        }
    }
}

@Composable
private fun ManualReleaseIdentitySection(
    formState: ManualReleaseFormState,
    onUpdateForm: (String, (ManualReleaseFormData) -> ManualReleaseFormData) -> Unit,
) {
    SectionTitle("Release")
    AccentCard {
        ManualTextInput(
            label = "Artist",
            required = true,
            value =
                formState.formData.artists
                    .firstOrNull()
                    .orEmpty(),
            error = formState.localFieldErrors["artists"],
            onValueChange = { value ->
                onUpdateForm("artists") { data ->
                    data.copy(artists = value.toSingleItemList())
                }
            },
        )
        ManualTextInput(
            label = "Title",
            required = true,
            value = formState.formData.title.orEmpty(),
            error = formState.localFieldErrors["title"],
            onValueChange = { value ->
                onUpdateForm("title") { data -> data.copy(title = value.toOptionalText()) }
            },
        )
        ManualTextInput(
            label = "Year",
            value = formState.formData.year?.toString() ?: "",
            error = formState.localFieldErrors["year"],
            onValueChange = { value ->
                val digitsOnly = value.filter { character -> character.isDigit() }.take(4)
                onUpdateForm("year") { data -> data.copy(year = digitsOnly.toIntOrNull()) }
            },
        )
        ManualTextInput(
            label = "Label",
            required = true,
            value = formState.formData.label.orEmpty(),
            error = formState.localFieldErrors["label"],
            onValueChange = { value ->
                onUpdateForm("label") { data -> data.copy(label = value.toOptionalText()) }
            },
        )
        ManualTextInput(
            label = "Catalog Number",
            value = formState.formData.catalogNumber.orEmpty(),
            error = formState.localFieldErrors["catalog_number"],
            onValueChange = { value ->
                onUpdateForm("catalog_number") { data -> data.copy(catalogNumber = value.toOptionalText()) }
            },
        )
        ManualTextInput(
            label = "Barcode",
            value = formState.formData.barcode.orEmpty(),
            error = formState.localFieldErrors["barcode"],
            onValueChange = { value ->
                onUpdateForm("barcode") { data -> data.copy(barcode = value.toOptionalText()) }
            },
        )
        ManualDropdown(
            label = "Genre",
            required = true,
            value = formState.formData.genres.firstOrNull(),
            placeholder = "Select genre",
            options = MANUAL_GENRES,
            onSelect = { genre ->
                onUpdateForm("genres") { data ->
                    data.copy(
                        genres = genre.toSingleItemList(),
                        styles = if (genre == "Electronic") data.styles else emptyList(),
                    )
                }
            },
        )
        if (formState.formData.genres.contains("Electronic")) {
            ManualDropdown(
                label = "Style",
                required = true,
                value = formState.formData.styles.firstOrNull(),
                placeholder = "Select style",
                options = ELECTRONIC_STYLES,
                onSelect = { style ->
                    onUpdateForm("styles") { data -> data.copy(styles = style.toSingleItemList()) }
                },
            )
        }
    }
}

@Composable
private fun ManualReleaseFormatSection(
    formState: ManualReleaseFormState,
    onUpdateForm: (String, (ManualReleaseFormData) -> ManualReleaseFormData) -> Unit,
) {
    SectionTitle("Format")
    AccentCard {
        ManualDropdown(
            label = "Format",
            required = true,
            value = formState.formData.format?.wireValue,
            placeholder = "Select format",
            options = ManualReleaseFormat.entries.map { it.wireValue },
            onSelect = { value ->
                val format = ManualReleaseFormat.fromWireValue(value)
                onUpdateForm("format") { data ->
                    data.copy(
                        format = format,
                        vinylSize = if (format == ManualReleaseFormat.Vinyl) data.vinylSize else null,
                        vinylSpeed = if (format == ManualReleaseFormat.Vinyl) data.vinylSpeed else null,
                        vinylDiscCount = if (format == ManualReleaseFormat.Vinyl) data.vinylDiscCount else null,
                    )
                }
            },
        )
        if (formState.formData.format == ManualReleaseFormat.Vinyl) {
            ManualDropdown(
                label = "Vinyl Size",
                required = true,
                value = formState.formData.vinylSize?.wireValue,
                placeholder = "Select size",
                options = ManualReleaseVinylSize.entries.map { it.wireValue },
                onSelect = { value ->
                    onUpdateForm("vinyl_size") { data -> data.copy(vinylSize = ManualReleaseVinylSize.fromWireValue(value)) }
                },
            )
            ManualDropdown(
                label = "Vinyl Speed",
                required = true,
                value = formState.formData.vinylSpeed?.wireValue,
                placeholder = "Select speed",
                options = ManualReleaseVinylSpeed.entries.map { it.wireValue },
                onSelect = { value ->
                    onUpdateForm("vinyl_speed") { data -> data.copy(vinylSpeed = ManualReleaseVinylSpeed.fromWireValue(value)) }
                },
            )
            ManualDropdown(
                label = "Vinyl Discs",
                required = true,
                value = formState.formData.vinylDiscCount?.toString(),
                placeholder = "Select disc count",
                options = (1..ManualReleaseLimits.MAX_VINYL_DISC_COUNT).map { it.toString() },
                error = formState.localFieldErrors["vinyl_disc_count"],
                onSelect = { value ->
                    onUpdateForm("vinyl_disc_count") { data -> data.copy(vinylDiscCount = value.toIntOrNull()) }
                },
            )
        }
    }
}

@Composable
private fun ManualReleaseCoverSection(
    formState: ManualReleaseFormState,
    previewImageUrl: String?,
    onSelectCover: () -> Unit,
    onClearSelectedCover: () -> Unit,
) {
    SectionTitle("Cover")
    AccentCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                imageUrl = previewImageUrl,
                contentDescription = "Manual release cover",
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = if (previewImageUrl.isNullOrBlank()) "No cover selected" else "Cover selected",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = formState.coverDetailsLabel(),
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ManualTextAction(
                label = if (previewImageUrl.isNullOrBlank()) "Choose Cover" else "Replace Cover",
                onClick = onSelectCover,
            )
            if (formState.coverUri != null) {
                ManualTextAction(
                    label = "Clear Selection",
                    onClick = onClearSelectedCover,
                    isSecondary = true,
                )
            }
        }
        formState.localFieldErrors["cover"]?.let { error ->
            ManualFieldError(error)
        }
    }
}

@Composable
private fun ManualReleaseTracklistSection(
    formState: ManualReleaseFormState,
    onUpdateForm: (String, (ManualReleaseFormData) -> ManualReleaseFormData) -> Unit,
) {
    SectionTitle("Tracklist")
    var expandedTrackIndexes by remember { mutableStateOf(setOf(0)) }
    var showEmptyTrackLimitDialog by remember { mutableStateOf(false) }
    val visibleTracks = formState.formData.tracklist.ifEmpty { listOf(ManualReleaseTrackInput()) }
    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
        visibleTracks.forEachIndexed { index, track ->
            ManualTrackCard(
                index = index,
                track = track,
                expanded = index in expandedTrackIndexes,
                canDelete = visibleTracks.size > 1 || track.hasTrackInput(),
                fieldErrors = formState.localFieldErrors,
                onToggleExpanded = {
                    expandedTrackIndexes =
                        if (index in expandedTrackIndexes) {
                            expandedTrackIndexes - index
                        } else {
                            expandedTrackIndexes + index
                        }
                },
                onUpdate = { updatedTrack ->
                    onUpdateForm("tracklist") { data ->
                        data.copy(tracklist = visibleTracks.replaceTrack(index, updatedTrack))
                    }
                },
                onDelete = {
                    expandedTrackIndexes =
                        expandedTrackIndexes
                            .filter { expandedIndex -> expandedIndex != index }
                            .map { expandedIndex -> if (expandedIndex > index) expandedIndex - 1 else expandedIndex }
                            .toSet()
                    onUpdateForm("tracklist") { data ->
                        data.copy(tracklist = visibleTracks.filterIndexed { itemIndex, _ -> itemIndex != index })
                    }
                },
            )
        }
        ManualInlineAction(
            label = "Add Track",
            onClick = {
                if (visibleTracks.count { it.isEmptyTrackForm() } >= MAX_EMPTY_TRACK_FORMS) {
                    showEmptyTrackLimitDialog = true
                } else {
                    val previousTrackIndex = visibleTracks.lastIndex
                    val newTrackIndex = visibleTracks.size
                    expandedTrackIndexes = (expandedTrackIndexes - previousTrackIndex) + newTrackIndex
                    onUpdateForm("tracklist") { data ->
                        data.copy(tracklist = visibleTracks + ManualReleaseTrackInput())
                    }
                }
            },
        )
        formState.localFieldErrors["tracklist"]?.let { error ->
            ManualFieldError(error)
        }
    }
    if (showEmptyTrackLimitDialog) {
        AlertDialog(
            onDismissRequest = { showEmptyTrackLimitDialog = false },
            title = { Text("Fill previous tracks") },
            text = { Text("You can keep up to two empty track forms. Fill one before adding another.") },
            confirmButton = {
                TextButton(onClick = { showEmptyTrackLimitDialog = false }) {
                    Text("Got it")
                }
            },
        )
    }
}

@Composable
private fun ManualTrackCard(
    index: Int,
    track: ManualReleaseTrackInput,
    expanded: Boolean,
    canDelete: Boolean,
    fieldErrors: Map<String, String>,
    onToggleExpanded: () -> Unit,
    onUpdate: (ManualReleaseTrackInput) -> Unit,
    onDelete: () -> Unit,
) {
    val credit = track.credits.firstOrNull()
    AccentCard {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable(
                        onClickLabel = if (expanded) "Collapse track" else "Expand track",
                        role = Role.Button,
                        onClick = onToggleExpanded,
                    ),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier = Modifier.weight(1f),
                text = trackHeaderLabel(index, track),
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(
                imageVector = if (expanded) Icons.Filled.KeyboardArrowDown else Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                contentDescription = null,
                tint = VinylColors.TextSecondary,
                modifier = Modifier.size(22.dp),
            )
            if (canDelete) {
                CircleIconButton(
                    icon = Icons.Filled.Delete,
                    contentDescription = "Delete track",
                    onClick = onDelete,
                    iconTint = VinylColors.AccentOrange,
                )
            }
        }
        if (expanded) {
            ManualTextInput(
                label = "Track Title",
                required = true,
                value = track.title.orEmpty(),
                error = fieldErrors["tracklist.$index.title"],
                onValueChange = { value -> onUpdate(track.copy(title = value.toOptionalText())) },
            )
            ManualTextInput(
                label = "Position",
                value = track.position.orEmpty(),
                error = fieldErrors["tracklist.$index.position"],
                onValueChange = { value -> onUpdate(track.copy(position = value.toOptionalText())) },
            )
            ManualTextInput(
                label = "Duration",
                value = track.duration.orEmpty(),
                error = fieldErrors["tracklist.$index.duration"],
                onValueChange = { value -> onUpdate(track.copy(duration = value.toOptionalText())) },
            )
            ManualDropdown(
                label = "Track Credit Role",
                value = credit?.role?.wireValue,
                placeholder = "No credit",
                options = listOf("No credit") + ManualReleaseTrackCreditRole.entries.map { it.wireValue },
                onSelect = { value ->
                    val role = ManualReleaseTrackCreditRole.fromWireValue(value)
                    onUpdate(
                        track.copy(
                            credits =
                                if (role == null) {
                                    emptyList()
                                } else {
                                    listOf(ManualReleaseTrackCreditInput(role = role, name = credit?.name))
                                },
                        ),
                    )
                },
            )
            if (credit != null) {
                ManualTextInput(
                    label = "Credit Name",
                    value = credit.name.orEmpty(),
                    error = fieldErrors["tracklist.$index.credits.0.name"],
                    onValueChange = { value ->
                        onUpdate(track.copy(credits = listOf(credit.copy(name = value.toOptionalText()))))
                    },
                )
            }
        }
    }
}

@Composable
private fun ManualFieldLabel(
    label: String,
    required: Boolean,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.labelMedium,
        )
        if (required) {
            Text(
                text = "*",
                color = VinylColors.AccentOrange,
                style = MaterialTheme.typography.labelMedium,
            )
        }
    }
}

@Composable
private fun ManualTextInput(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    error: String? = null,
    required: Boolean = false,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
    ) {
        ManualFieldLabel(label = label, required = required)
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(54.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfaceSecondary)
                    .border(1.dp, if (error == null) VinylColors.BorderDefault else VinylColors.AccentOrange, VinylShapes.Card)
                    .padding(horizontal = VinylSpacing.SpaceLg),
            contentAlignment = Alignment.CenterStart,
        ) {
            BasicTextField(
                modifier = Modifier.fillMaxWidth(),
                value = value,
                onValueChange = onValueChange,
                singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
                textStyle = MaterialTheme.typography.bodyMedium.copy(color = VinylColors.TextPrimary),
                cursorBrush = SolidColor(VinylColors.AccentGreen),
                decorationBox = { innerTextField ->
                    if (value.isBlank()) {
                        Text(
                            text = label,
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    innerTextField()
                },
            )
        }
        error?.let { ManualFieldError(it) }
    }
}

@Composable
private fun ManualDropdown(
    label: String,
    value: String?,
    placeholder: String,
    options: List<String>,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
    error: String? = null,
    required: Boolean = false,
) {
    var expanded by remember { mutableStateOf(false) }
    var selectorWidth by remember { mutableStateOf(Dp.Unspecified) }
    val focusManager = LocalFocusManager.current
    val density = LocalDensity.current
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
    ) {
        ManualFieldLabel(label = label, required = required)
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .onGloballyPositioned { coordinates ->
                        selectorWidth = with(density) { coordinates.size.width.toDp() }
                    },
        ) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .clip(VinylShapes.Card)
                        .background(VinylColors.SurfacePrimary)
                        .border(1.dp, if (error == null) VinylColors.BorderDefault else VinylColors.AccentOrange, VinylShapes.Card)
                        .clickable(
                            onClickLabel = label,
                            role = Role.Button,
                            onClick = { expanded = !expanded },
                        ).padding(horizontal = VinylSpacing.SpaceMd)
                        .height(56.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    modifier = Modifier.weight(1f),
                    text = value?.takeIf { it.isNotBlank() } ?: placeholder,
                    color = if (value.isNullOrBlank()) VinylColors.TextSecondary else VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Icon(
                    imageVector = if (expanded) Icons.Filled.KeyboardArrowDown else Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                    contentDescription = null,
                    tint = VinylColors.TextSecondary,
                    modifier = Modifier.size(28.dp),
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
                                .width(selectorWidth.takeIf { it != Dp.Unspecified } ?: 240.dp)
                                .heightIn(max = 320.dp)
                                .shadow(4.dp, VinylShapes.Card)
                                .clip(VinylShapes.Card)
                                .background(VinylColors.SurfacePrimary)
                                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                                .verticalScroll(rememberScrollState()),
                    ) {
                        options.forEachIndexed { index, option ->
                            ManualDropdownOptionRow(
                                label = option,
                                selected = option == value,
                                alternate = index % 2 == 0,
                                onClickLabel = "Select $option",
                                onClick = {
                                    expanded = false
                                    focusManager.clearFocus(force = true)
                                    onSelect(option)
                                },
                            )
                        }
                    }
                }
            }
        }
        error?.let { ManualFieldError(it) }
    }
}

@Composable
private fun ManualInlineAction(
    label: String,
    onClick: () -> Unit,
) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .height(48.dp)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = VinylColors.AccentGreen,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun ManualTextAction(
    label: String,
    onClick: () -> Unit,
    isSecondary: Boolean = false,
) {
    Box(
        modifier =
            Modifier
                .height(44.dp)
                .clip(VinylShapes.Card)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = VinylSpacing.SpaceSm),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = if (isSecondary) VinylColors.TextSecondary else VinylColors.AccentGreen,
            style = MaterialTheme.typography.labelLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun ManualSaveErrorCard(message: String) {
    AccentCard(borderColor = VinylColors.AccentOrange.copy(alpha = 0.35f)) {
        Text(
            text = message,
            color = VinylColors.AccentOrange,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun ManualFormLoadingCard() {
    AccentCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(24.dp),
                color = VinylColors.AccentGreen,
                strokeWidth = 2.dp,
            )
            Text(
                text = "Loading draft",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ManualReleaseFormBottomActions(
    primaryAction: ManualReleasePrimaryAction,
    isSaving: Boolean,
    isLoading: Boolean,
    onCancel: () -> Unit,
    onSave: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd)
                .padding(top = VinylSpacing.SpaceLg, bottom = 32.dp),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
    ) {
        ManualFormCancelButton(onClick = onCancel, modifier = Modifier.weight(1f))
        ManualFormSaveButton(
            label =
                when {
                    isLoading -> "Loading..."
                    isSaving -> "Saving..."
                    primaryAction == ManualReleasePrimaryAction.DisabledSave -> "Save"
                    primaryAction == ManualReleasePrimaryAction.SaveDraft -> "Save Draft"
                    else -> "Save as"
                },
            enabled = !isLoading && !isSaving && primaryAction != ManualReleasePrimaryAction.DisabledSave,
            onClick = onSave,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun ManualFormCancelButton(
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
private fun ManualFormSaveButton(
    label: String,
    enabled: Boolean,
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
                .alpha(if (enabled) 1f else 0.55f)
                .clip(VinylShapes.Card)
                .background(brush)
                .border(1.dp, VinylColors.GreenBorder30, VinylShapes.Card)
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
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun ManualDropdownOptionRow(
    label: String,
    selected: Boolean,
    alternate: Boolean,
    onClickLabel: String,
    onClick: () -> Unit,
) {
    val rowColor = if (alternate) VinylColors.SurfacePrimary else VinylColors.SurfaceSecondary
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .background(rowColor)
                .clickable(
                    role = Role.RadioButton,
                    onClickLabel = onClickLabel,
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
                    .background(if (selected) VinylColors.AccentGreen else VinylColors.SurfacePrimary)
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

@Composable
private fun ManualFieldError(message: String) {
    Text(
        text = message,
        color = VinylColors.AccentOrange,
        style = MaterialTheme.typography.bodySmall,
    )
}

private suspend fun uploadSelectedCoverIfNeeded(
    context: Context,
    repository: ManualReleaseRepository,
    draftId: String,
    formState: ManualReleaseFormState,
) {
    val coverUri = formState.coverUri ?: return
    repository.uploadCover(context, draftId, Uri.parse(coverUri))
}

private fun ManualReleaseFormUiState.hasUnsavedChanges(): Boolean =
    formState.normalizedForChangeCheck() != initialFormState.normalizedForChangeCheck()

private fun ManualReleaseDraft.toFormState(): ManualReleaseFormState =
    ManualReleaseFormState(
        formData = formData,
        coverContentType = coverContentType,
        coverSizeBytes = coverSizeBytes,
    )

private fun ManualReleaseFormState.normalizedForChangeCheck(): ManualReleaseFormState =
    copy(
        formData = formData.normalizedForManualSubmit(),
        dirtyFields = emptySet(),
        fieldErrors = emptyMap(),
    )

private fun ManualReleaseFormState.selectedCoverError(): String? =
    if (coverUri == null || coverValidationState == ManualReleaseCoverValidationState.Valid) {
        null
    } else {
        localFieldErrors["cover"] ?: "Cover image could not be uploaded."
    }

private fun ManualReleaseFormState.coverDetailsLabel(): String {
    val contentLabel = coverContentType?.toCoverContentLabel()
    val sizeLabel = coverSizeBytes?.toCoverSizeLabel()
    return listOfNotNull(contentLabel, sizeLabel)
        .takeIf { it.isNotEmpty() }
        ?.joinToString(" / ")
        ?: "JPEG, PNG, or WebP up to 500 KB; longest side 100-1200 px"
}

private fun String.toCoverContentLabel(): String =
    when (lowercase()) {
        "image/jpeg" -> "JPEG"
        "image/png" -> "PNG"
        "image/webp" -> "WebP"
        else -> this
    }

private fun Int.toCoverSizeLabel(): String {
    val mbTenths = this.toLong() * 10 / (1024 * 1024)
    return if (mbTenths >= 10) {
        "${mbTenths / 10}.${mbTenths % 10} MB"
    } else {
        "${(this / 1024).coerceAtLeast(1)} KB"
    }
}

private fun Context.readSelectedCoverMetadata(uri: Uri): SelectedCoverMetadata {
    val contentType = contentResolver.getType(uri)?.lowercase()
    val sizeBytes =
        contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (sizeIndex >= 0 && cursor.moveToFirst() && !cursor.isNull(sizeIndex)) {
                cursor.getLong(sizeIndex).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
            } else {
                null
            }
        }
    val imageBounds =
        contentResolver.openInputStream(uri)?.use { inputStream ->
            val options = BitmapFactory.Options()
            options.inJustDecodeBounds = true
            BitmapFactory.decodeStream(inputStream, null, options)
            options.takeIf { bounds -> bounds.outWidth > 0 && bounds.outHeight > 0 }
        }
    return SelectedCoverMetadata(
        contentType = contentType,
        sizeBytes = sizeBytes,
        widthPx = imageBounds?.outWidth,
        heightPx = imageBounds?.outHeight,
    )
}

private fun ManualReleaseFormData.normalizedForManualSubmit(): ManualReleaseFormData =
    copy(
        artists = artists.mapNotNull { it.trim().takeIf(String::isNotBlank) },
        title = title?.trim()?.takeIf(String::isNotBlank),
        label = label?.trim()?.takeIf(String::isNotBlank),
        catalogNumber = catalogNumber?.trim()?.takeIf(String::isNotBlank),
        barcode = barcode?.trim()?.takeIf(String::isNotBlank),
        genres = genres.mapNotNull { it.trim().takeIf(String::isNotBlank) },
        styles = styles.mapNotNull { it.trim().takeIf(String::isNotBlank) },
        tracklist = tracklist.normalizedTracklist(),
    )

private fun String.toOptionalText(): String? = takeIf { it.isNotEmpty() }

private fun String.toSingleItemList(): List<String> = takeIf { it.isNotBlank() }?.let(::listOf).orEmpty()

private fun trackHeaderLabel(
    index: Int,
    track: ManualReleaseTrackInput,
): String =
    track.title
        ?.takeIf { it.isNotBlank() }
        ?.let { title -> "Track ${index + 1} - $title" }
        ?: "Track ${index + 1}"

private fun ManualReleaseTrackInput.hasTrackInput(): Boolean =
    !title.isNullOrBlank() ||
        !position.isNullOrBlank() ||
        !duration.isNullOrBlank() ||
        credits.isNotEmpty()

private fun ManualReleaseTrackInput.isEmptyTrackForm(): Boolean = !hasTrackInput()

private fun List<ManualReleaseTrackInput>.replaceTrack(
    index: Int,
    track: ManualReleaseTrackInput,
): List<ManualReleaseTrackInput> =
    mapIndexed { itemIndex, item ->
        if (itemIndex == index) track else item
    }

private fun List<ManualReleaseTrackInput>.normalizedTracklist(): List<ManualReleaseTrackInput> =
    mapNotNull { track ->
        val normalizedCredits =
            track.credits.map { credit ->
                credit.copy(name = credit.name?.trim()?.takeIf(String::isNotBlank))
            }
        track
            .copy(
                title = track.title?.trim()?.takeIf(String::isNotBlank),
                position = track.position?.trim()?.takeIf(String::isNotBlank),
                duration = track.duration?.trim()?.takeIf(String::isNotBlank),
                credits = normalizedCredits,
            ).takeIf { it.hasTrackInput() }
    }
