package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.data.manual.ManualReleaseRepository
import com.example.vinyllistenapp.domain.ManualReleaseDraftSummary
import com.example.vinyllistenapp.domain.ManualReleaseLimits
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.CircleIconButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.FloatingGlassButton
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

private data class ManualSubmissionsUiState(
    val drafts: List<ManualReleaseDraftSummary> = emptyList(),
    val draftLimit: Int = ManualReleaseLimits.MAX_DRAFTS,
    val remainingSlots: Int = ManualReleaseLimits.MAX_DRAFTS,
    val isLoading: Boolean = true,
    val deletingDraftId: String? = null,
    val errorMessage: String? = null,
)

@Composable
fun ManualSubmissionsScreen(
    apiClient: VinylApiClient,
    refreshKey: Int = 0,
    onHome: () -> Unit,
    onStats: () -> Unit,
    onInsights: () -> Unit,
    onCollection: () -> Unit,
    onAddRelease: () -> Unit,
    onOpenDraft: (String) -> Unit,
) {
    val repository = remember(apiClient) { ManualReleaseRepository(apiClient) }
    val scope = rememberCoroutineScope()
    var state by remember { mutableStateOf(ManualSubmissionsUiState()) }
    var retryKey by remember { mutableIntStateOf(0) }
    var draftPendingDelete by remember { mutableStateOf<ManualReleaseDraftSummary?>(null) }
    var showDraftCapDialog by remember { mutableStateOf(false) }

    suspend fun loadDrafts() {
        state = state.copy(isLoading = true, errorMessage = null)
        runCatching { repository.listDrafts() }
            .onSuccess { draftList ->
                state =
                    state.copy(
                        drafts = draftList.items.take(draftList.limit),
                        draftLimit = draftList.limit,
                        remainingSlots = draftList.remainingSlots,
                        isLoading = false,
                        errorMessage = null,
                    )
            }.onFailure { failure ->
                state =
                    state.copy(
                        drafts = emptyList(),
                        isLoading = false,
                        errorMessage = failure.toUserMessage("Could not load manual release drafts."),
                    )
            }
    }

    fun requestAddRelease() {
        if (state.remainingSlots <= 0 || state.drafts.size >= state.draftLimit) {
            showDraftCapDialog = true
        } else {
            onAddRelease()
        }
    }

    fun deleteDraft(draft: ManualReleaseDraftSummary) {
        if (state.deletingDraftId != null) return
        scope.launch {
            state = state.copy(deletingDraftId = draft.id, errorMessage = null)
            runCatching { repository.deleteDraft(draft.id) }
                .onSuccess {
                    draftPendingDelete = null
                    state = state.copy(deletingDraftId = null)
                    loadDrafts()
                    state = state.copy(deletingDraftId = null)
                }.onFailure { failure ->
                    state =
                        state.copy(
                            deletingDraftId = null,
                            errorMessage = failure.toUserMessage("Could not delete manual release draft."),
                        )
                }
        }
    }

    LaunchedEffect(repository, retryKey, refreshKey) {
        loadDrafts()
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Analytics", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onInsights),
                        BottomNavItem("Collection", Icons.Filled.LibraryMusic, selected = true, onClick = onCollection),
                    ),
            )
        },
        floatingActionButton = {
            FloatingGlassButton(
                label = "Add Release",
                onClick = ::requestAddRelease,
                modifier =
                    Modifier.padding(
                        end = VinylSpacing.SpaceMd,
                        bottom = VinylSpacing.SpaceLg,
                    ),
            )
        },
    ) { innerPadding ->
        ManualSubmissionsContent(
            state = state,
            innerPadding = innerPadding,
            onRetry = { retryKey += 1 },
            onDeleteDraft = { draftPendingDelete = it },
            onOpenDraft = onOpenDraft,
        )
    }

    draftPendingDelete?.let { draft ->
        DeleteManualDraftDialog(
            draft = draft,
            isDeleting = state.deletingDraftId == draft.id,
            onConfirm = { deleteDraft(draft) },
            onDismiss = {
                if (state.deletingDraftId != draft.id) {
                    draftPendingDelete = null
                }
            },
        )
    }

    if (showDraftCapDialog) {
        ManualDraftCapDialog(
            draftLimit = state.draftLimit,
            onDismiss = { showDraftCapDialog = false },
        )
    }
}

@Composable
private fun ManualSubmissionsContent(
    state: ManualSubmissionsUiState,
    innerPadding: PaddingValues,
    onRetry: () -> Unit,
    onDeleteDraft: (ManualReleaseDraftSummary) -> Unit,
    onOpenDraft: (String) -> Unit,
) {
    ScreenContent(
        title = "Manual Submissions",
        subtitle = "Add releases manually to your collection and save or manage drafts.",
        innerPadding = innerPadding,
    ) {
        SectionTitle("Drafts")
        when {
            state.isLoading -> ManualSubmissionsLoadingCard()
            else -> {
                state.errorMessage?.let { message ->
                    ErrorRetryCard(message = message, onRetry = onRetry)
                }
                if (state.drafts.isEmpty()) {
                    ManualSubmissionsEmptyCard()
                } else {
                    state.drafts.forEach { draft ->
                        ManualReleaseDraftCard(
                            draft = draft,
                            isDeleting = state.deletingDraftId == draft.id,
                            onClick = { onOpenDraft(draft.id) },
                            onDelete = { onDeleteDraft(draft) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ManualSubmissionsLoadingCard() {
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
                text = "Loading drafts",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ManualSubmissionsEmptyCard() {
    AccentCard {
        Text(
            text = "No saved drafts yet.",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            text = "Use Add Release when you are ready to start entering a record manually.",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun ManualReleaseDraftCard(
    draft: ManualReleaseDraftSummary,
    isDeleting: Boolean,
    onClick: () -> Unit,
    onDelete: () -> Unit,
) {
    AccentCard(
        modifier =
            Modifier
                .heightIn(min = 132.dp)
                .clickable(
                    onClickLabel = "Open manual release draft",
                    role = Role.Button,
                    onClick = onClick,
                ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            verticalAlignment = Alignment.Top,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                compact = false,
                imageUrl = draft.coverThumbnailUrl,
                contentDescription = "${manualDraftTitle(draft)} cover art",
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = draft.artist?.takeIf { it.isNotBlank() } ?: "Unknown artist",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = manualDraftTitle(draft),
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = manualDraftMetadata(draft),
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ManualDraftStatusChip(requiredComplete = draft.completionState?.requiredComplete == true)
                    Text(
                        modifier = Modifier.weight(1f),
                        text = "Updated ${relativeLastPlayedLabel(draft.updatedAt)}",
                        color = VinylColors.TextSecondary,
                        textAlign = TextAlign.End,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            CircleIconButton(
                icon = Icons.Filled.Delete,
                contentDescription = "Delete draft",
                onClick = onDelete,
                iconTint = VinylColors.AccentOrange,
            )
        }
        if (isDeleting) {
            Text(
                text = "Deleting draft",
                color = VinylColors.AccentOrange,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ManualDraftStatusChip(requiredComplete: Boolean) {
    val label = if (requiredComplete) "Ready to save" else "Draft in progress"
    val accent = if (requiredComplete) VinylColors.AccentGreen else VinylColors.AccentPurple
    Box(
        modifier =
            Modifier
                .clip(VinylShapes.Chip)
                .background(accent.copy(alpha = 0.18f))
                .border(1.dp, accent.copy(alpha = 0.35f), VinylShapes.Chip)
                .padding(horizontal = VinylSpacing.SpaceMd, vertical = VinylSpacing.SpaceXs),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = accent,
            style = MaterialTheme.typography.labelSmall,
            maxLines = 1,
        )
    }
}

@Composable
private fun DeleteManualDraftDialog(
    draft: ManualReleaseDraftSummary,
    isDeleting: Boolean,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Delete draft?") },
        text = { Text("Delete “${manualDraftTitle(draft)}” from Manual Submissions?") },
        confirmButton = {
            TextButton(
                enabled = !isDeleting,
                onClick = onConfirm,
            ) {
                Text("Delete")
            }
        },
        dismissButton = {
            TextButton(
                enabled = !isDeleting,
                onClick = onDismiss,
            ) {
                Text("Cancel")
            }
        },
    )
}

@Composable
private fun ManualDraftCapDialog(
    draftLimit: Int,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Draft limit reached") },
        text = { Text("You can save up to $draftLimit manual release drafts. Delete or complete a draft before adding another.") },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Got it")
            }
        },
    )
}

private fun manualDraftTitle(draft: ManualReleaseDraftSummary): String = draft.title?.takeIf { it.isNotBlank() } ?: "Untitled release"

private fun manualDraftMetadata(draft: ManualReleaseDraftSummary): String =
    listOfNotNull(
        draft.labelCatalogLabel(),
        draft.format?.takeIf { it.isNotBlank() },
    ).joinToString(" • ").ifBlank { "No label or format yet" }

private fun ManualReleaseDraftSummary.labelCatalogLabel(): String? {
    val labelValue = label?.takeIf { it.isNotBlank() }
    val catalogValue = catalogNumber?.takeIf { it.isNotBlank() }
    return when {
        labelValue != null && catalogValue != null -> "$labelValue • $catalogValue"
        labelValue != null -> labelValue
        catalogValue != null -> catalogValue
        else -> null
    }
}
