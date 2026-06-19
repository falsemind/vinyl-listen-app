package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Album
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.navigation.VinylRoutes
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun RecordActionItemsScreen(
    releaseId: String?,
    actionType: String?,
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenArtistCollection: (String) -> Unit,
    onOpenLabelCollection: (String) -> Unit,
) {
    val mode = remember(actionType) { RecordActionItemsMode.fromRoute(actionType) }
    val uriHandler = LocalUriHandler.current
    var record by remember(releaseId) { mutableStateOf<RecordSummary?>(null) }
    var isLoading by remember(releaseId) { mutableStateOf(true) }
    var error by remember(releaseId) { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }
    val scrollState = rememberScrollState()

    LaunchedEffect(releaseId, retryKey) {
        val currentReleaseId = releaseId
        if (currentReleaseId.isNullOrBlank()) {
            record = null
            error = "Missing release."
            isLoading = false
            return@LaunchedEffect
        }
        isLoading = true
        runCatching { apiClient.getRelease(currentReleaseId) }
            .onSuccess { release ->
                record = release
                error = null
            }.onFailure { failure ->
                record = null
                error = failure.toUserMessage("Could not load release artists.")
            }
        isLoading = false
    }

    val items =
        record
            ?.let { release ->
                recordActionItems(
                    record = release,
                    mode = mode,
                    openUri = uriHandler::openUri,
                    onOpenArtistCollection = onOpenArtistCollection,
                    onOpenLabelCollection = onOpenLabelCollection,
                )
            }.orEmpty()

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .verticalScroll(scrollState)
                .padding(horizontal = VinylSpacing.SpaceMd)
                .padding(top = 48.dp, bottom = VinylSpacing.Space2Xl),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier =
                    Modifier
                        .weight(1f)
                        .padding(end = VinylSpacing.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = mode.title,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.headlineLarge,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                record?.title?.takeIf { it.isNotBlank() }?.let { title ->
                    Text(
                        text = title,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            CloseCircleButton(onClick = onBack, contentDescription = "Close ${mode.title.lowercase()}")
        }
        LocalTimedSessionBanner.current?.invoke()
        error?.let { message ->
            ErrorRetryCard(message = message, onRetry = { retryKey += 1 })
        }
        if (isLoading) {
            Text(
                modifier = Modifier.fillMaxWidth(),
                text = "Loading...",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        if (!isLoading && error == null && items.isEmpty()) {
            Text(
                modifier = Modifier.fillMaxWidth(),
                text = mode.emptyMessage,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        items.forEach { item ->
            RecordActionItemCard(item = item)
        }
        Spacer(Modifier.height(96.dp))
    }
}

@Composable
private fun RecordActionItemCard(item: RecordActionItem) {
    AccentCard(
        modifier =
            Modifier.clickable(
                onClickLabel = item.onClickLabel,
                role = Role.Button,
                onClick = item.onClick,
            ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier =
                    Modifier
                        .weight(1f)
                        .padding(end = VinylSpacing.SpaceMd),
                text = item.label,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(
                modifier = Modifier.size(40.dp),
                imageVector = item.icon,
                contentDescription = null,
                tint = VinylColors.AccentGreen,
            )
        }
    }
}

private fun recordActionItems(
    record: RecordSummary,
    mode: RecordActionItemsMode,
    openUri: (String) -> Unit,
    onOpenArtistCollection: (String) -> Unit,
    onOpenLabelCollection: (String) -> Unit,
): List<RecordActionItem> =
    when (mode) {
        RecordActionItemsMode.CollectionArtists ->
            collectionArtistNames(record).map { artistName ->
                RecordActionItem(
                    label = artistName,
                    icon = Icons.Filled.Person,
                    onClickLabel = "Filter collection by $artistName",
                    onClick = { onOpenArtistCollection(artistName) },
                )
            }

        RecordActionItemsMode.CollectionLabels ->
            collectionLabelNames(record).map { labelName ->
                RecordActionItem(
                    label = labelName,
                    icon = Icons.Filled.Album,
                    onClickLabel = "Filter collection by $labelName",
                    onClick = { onOpenLabelCollection(labelName) },
                )
            }

        RecordActionItemsMode.DiscogsArtists ->
            discogsArtistRows(record).map { artist ->
                val displayArtistName = cleanDiscogsDisplayName(artist.name)
                RecordActionItem(
                    label = displayArtistName,
                    icon = Icons.Filled.Person,
                    onClickLabel = "Open $displayArtistName on Discogs",
                    onClick = {
                        openUri(
                            if (artist.discogsArtistId > 0) {
                                discogsArtistUrl(artist.discogsArtistId)
                            } else {
                                discogsArtistSearchUrl(displayArtistName)
                            },
                        )
                    },
                )
            }

        RecordActionItemsMode.DiscogsLabels ->
            collectionLabelNames(record).map { labelName ->
                RecordActionItem(
                    label = labelName,
                    icon = Icons.Filled.Album,
                    onClickLabel = "Open $labelName on Discogs",
                    onClick = { openUri(discogsLabelSearchUrl(labelName)) },
                )
            }
    }

private data class RecordActionItem(
    val label: String,
    val icon: ImageVector,
    val onClickLabel: String,
    val onClick: () -> Unit,
)

private enum class RecordActionItemsMode(
    val title: String,
    val emptyMessage: String,
) {
    CollectionArtists(
        title = "All release artists",
        emptyMessage = "No release artists.",
    ),
    CollectionLabels(
        title = "All release labels",
        emptyMessage = "No release labels.",
    ),
    DiscogsArtists(
        title = "All release artists",
        emptyMessage = "No release artists.",
    ),
    DiscogsLabels(
        title = "All release labels",
        emptyMessage = "No release labels.",
    ),
    ;

    companion object {
        fun fromRoute(actionType: String?): RecordActionItemsMode =
            when (actionType) {
                VinylRoutes.RECORD_ACTION_COLLECTION_LABELS -> CollectionLabels
                VinylRoutes.RECORD_ACTION_DISCOGS_ARTISTS -> DiscogsArtists
                VinylRoutes.RECORD_ACTION_DISCOGS_LABELS -> DiscogsLabels
                else -> CollectionArtists
            }
    }
}
