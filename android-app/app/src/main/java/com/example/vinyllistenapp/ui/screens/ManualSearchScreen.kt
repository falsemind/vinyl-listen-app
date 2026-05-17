package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.ReleaseSearchResult
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

@Composable
fun ManualSearchScreen(
    apiClient: VinylApiClient,
    onSelectRecord: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val pageSize = 10
    val scope = rememberCoroutineScope()
    var artistQuery by rememberSaveable { mutableStateOf("") }
    var titleQuery by rememberSaveable { mutableStateOf("") }
    var catalogQuery by rememberSaveable { mutableStateOf("") }
    var barcodeQuery by rememberSaveable { mutableStateOf("") }
    var yearQuery by rememberSaveable { mutableStateOf("") }
    var state by remember { mutableStateOf<ManualSearchUiState>(ManualSearchUiState.Idle) }
    var selectingDiscogsReleaseId by remember { mutableStateOf<Long?>(null) }

    fun runSearch(loadMore: Boolean = false) {
        val artist = artistQuery.trim()
        val title = titleQuery.trim()
        val catalog = catalogQuery.trim()
        val barcode = barcodeQuery.trim()
        val year = yearQuery.trim().takeIf { it.isNotBlank() }?.toIntOrNull()
        val hasSearchTerm =
            listOf(artist, title, catalog, barcode).any { it.isNotBlank() } || year != null
        if (!hasSearchTerm) {
            state = ManualSearchUiState.Error("Enter at least one search field.")
            return
        }

        scope.launch {
            val currentResults = (state as? ManualSearchUiState.Success)?.results.orEmpty()
            val offset = if (loadMore) currentResults.size else 0
            state =
                if (loadMore && currentResults.isNotEmpty()) {
                    ManualSearchUiState.Success(currentResults, hasMore = true, isLoadingMore = true)
                } else {
                    ManualSearchUiState.Loading
                }
            val results =
                runCatching {
                    apiClient.searchReleases(
                        artist = artist,
                        title = title,
                        catalog = catalog,
                        barcode = barcode,
                        year = year,
                        limit = pageSize,
                        offset = offset,
                    )
                }.getOrElse { error ->
                    if (loadMore && currentResults.isNotEmpty()) {
                        state = ManualSearchUiState.Success(currentResults, hasMore = true)
                        return@launch
                    }
                    state = ManualSearchUiState.Error(error.toUserMessage("Search failed. Retry in a moment."))
                    return@launch
                }
            val combinedResults = if (loadMore) currentResults + results else results
            state =
                if (combinedResults.isEmpty()) {
                    ManualSearchUiState.Empty
                } else {
                    ManualSearchUiState.Success(
                        results = combinedResults,
                        hasMore = results.size == pageSize,
                    )
                }
        }
    }

    fun selectResult(result: ReleaseSearchResult) {
        if (selectingDiscogsReleaseId != null) {
            return
        }
        selectingDiscogsReleaseId = result.discogsReleaseId
        scope.launch {
            val releaseId =
                runCatching { apiClient.importRelease(result.discogsReleaseId) }
                    .getOrElse { error ->
                        selectingDiscogsReleaseId = null
                        state = ManualSearchUiState.Error(error.toUserMessage("Could not import that record. Retry."))
                        return@launch
                    }
            selectingDiscogsReleaseId = null
            onSelectRecord(releaseId)
        }
    }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceMd),
    ) {
        ManualSearchHeader(onDismiss = onDismiss)
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = "Search for your record manually",
            color = VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        Column(
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            ManualSearchField(
                label = "Artist",
                placeholder = "Search by artist name",
                value = artistQuery,
                onValueChange = { artistQuery = it },
            )
            ManualSearchField(
                label = "Title",
                placeholder = "Search by album title",
                value = titleQuery,
                onValueChange = { titleQuery = it },
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                ManualSearchField(
                    label = "Catalog Number",
                    placeholder = "Cat #",
                    value = catalogQuery,
                    onValueChange = { catalogQuery = it },
                    modifier = Modifier.weight(1f),
                )
                ManualSearchField(
                    label = "Year",
                    placeholder = "Year",
                    value = yearQuery,
                    onValueChange = { yearQuery = it.filter(Char::isDigit).take(4) },
                    modifier = Modifier.weight(1f),
                )
            }
            ManualSearchField(
                label = "Barcode",
                placeholder = "Search by barcode",
                value = barcodeQuery,
                onValueChange = { barcodeQuery = it },
            )
        }
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        GlassPrimaryButton(
            label = if (state == ManualSearchUiState.Loading) "Searching" else "Search",
            onClick = {
                if (state != ManualSearchUiState.Loading && selectingDiscogsReleaseId == null) {
                    runSearch()
                }
            },
        )
        Spacer(Modifier.height(VinylSpacing.SpaceXl))
        Text(
            text = "Results",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(VinylSpacing.SpaceMd))
        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            when (val currentState = state) {
                ManualSearchUiState.Idle -> Unit
                ManualSearchUiState.Loading -> ManualSearchMessage("Searching Discogs...")
                ManualSearchUiState.Empty -> ManualSearchMessage("No results found.")
                is ManualSearchUiState.Error -> ManualSearchMessage(currentState.message, isError = true)
                is ManualSearchUiState.Success -> {
                    currentState.results.forEach { result ->
                        val isImporting = selectingDiscogsReleaseId != null
                        ManualSearchResultRow(
                            record = result,
                            isSelecting = selectingDiscogsReleaseId == result.discogsReleaseId,
                            enabled = !isImporting,
                            onClick = { selectResult(result) },
                        )
                    }
                    if (currentState.hasMore) {
                        ShowMoreButton(
                            isLoading = currentState.isLoadingMore,
                            onClick = { if (!currentState.isLoadingMore) runSearch(loadMore = true) },
                        )
                    }
                }
            }
            Spacer(Modifier.height(VinylSpacing.SpaceXl))
        }
    }
}

private sealed interface ManualSearchUiState {
    data object Idle : ManualSearchUiState

    data object Loading : ManualSearchUiState

    data object Empty : ManualSearchUiState

    data class Success(
        val results: List<ReleaseSearchResult>,
        val hasMore: Boolean,
        val isLoadingMore: Boolean = false,
    ) : ManualSearchUiState

    data class Error(
        val message: String,
    ) : ManualSearchUiState
}

@Composable
private fun ShowMoreButton(
    isLoading: Boolean,
    onClick: () -> Unit,
) {
    Text(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Chip)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Chip)
                .clickable(
                    enabled = !isLoading,
                    onClickLabel = "Show more results",
                    role = Role.Button,
                    onClick = onClick,
                ).padding(vertical = VinylSpacing.SpaceMd),
        text = if (isLoading) "Loading..." else "Show more",
        color = VinylColors.AccentGreen,
        textAlign = TextAlign.Center,
        style = MaterialTheme.typography.labelLarge,
    )
}

@Composable
private fun ManualSearchMessage(
    message: String,
    isError: Boolean = false,
) {
    Text(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(vertical = VinylSpacing.SpaceMd),
        text = message,
        color = if (isError) VinylColors.AccentOrange else VinylColors.TextSecondary,
        textAlign = TextAlign.Center,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun ManualSearchHeader(onDismiss: () -> Unit) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceLg),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CloseCircleButton(onClick = onDismiss)
        Text(
            text = "Manual Search",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.width(40.dp))
    }
}

@Composable
private fun ManualSearchField(
    label: String,
    placeholder: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp),
        )
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                    .padding(horizontal = VinylSpacing.SpaceLg),
            contentAlignment = Alignment.CenterStart,
        ) {
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                textStyle =
                    MaterialTheme.typography.bodyMedium.copy(
                        color = VinylColors.TextPrimary,
                    ),
                cursorBrush = SolidColor(VinylColors.AccentGreen),
                decorationBox = { innerTextField ->
                    if (value.isEmpty()) {
                        Text(
                            text = placeholder,
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    innerTextField()
                },
            )
        }
    }
}

@Composable
private fun ManualSearchResultRow(
    record: ReleaseSearchResult,
    isSelecting: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier =
            Modifier.clickable(
                enabled = enabled,
                onClickLabel = "Select ${record.title}",
                role = Role.Button,
                onClick = onClick,
            ),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceXs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(
                accentColor = VinylColors.AccentGreen,
                compact = true,
                imageUrl = record.thumbnailUrl,
                contentDescription = "${record.title} cover art",
            )
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = record.artist,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = if (isSelecting) "Importing..." else record.title,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = listOfNotNull(record.format, record.year?.toString()).joinToString(" - ").ifBlank { "Unknown format" },
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = "-",
                        color = VinylColors.BorderDefault,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = record.label ?: "Unknown label",
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
