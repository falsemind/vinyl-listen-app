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
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
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
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch
import java.time.Year

private const val RELEASE_YEAR_MIN = 1900
private const val RELEASE_YEAR_DIGITS = 4
private const val BARCODE_MIN_DIGITS = 8
private const val BARCODE_MAX_DIGITS = 14
private const val MANUAL_SEARCH_TEXT_MAX_CHARS = 100

@Composable
fun ManualSearchScreen(
    apiClient: VinylApiClient,
    onSelectRecord: (String) -> Unit,
    onDismiss: () -> Unit,
    mode: ManualSearchMode = ManualSearchMode.Discogs,
    initialBarcode: String = "",
) {
    val pageSize = 10
    val focusManager = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    var artistQuery by rememberSaveable { mutableStateOf("") }
    var titleQuery by rememberSaveable { mutableStateOf("") }
    var catalogQuery by rememberSaveable { mutableStateOf("") }
    var barcodeQuery by rememberSaveable(initialBarcode) {
        mutableStateOf(initialBarcode.digitsOnly(maxLength = BARCODE_MAX_DIGITS))
    }
    var yearQuery by rememberSaveable { mutableStateOf("") }
    var state by remember { mutableStateOf<ManualSearchUiState>(ManualSearchUiState.Idle) }
    var selectingDiscogsReleaseId by remember { mutableStateOf<Long?>(null) }
    var retryError by remember { mutableStateOf<String?>(null) }
    var failedImportResult by remember { mutableStateOf<ReleaseSearchResult?>(null) }
    val yearValidationError = validateReleaseYear(yearQuery)
    val barcodeValidationError = if (mode == ManualSearchMode.Discogs) validateBarcode(barcodeQuery) else null
    val effectiveBarcodeQuery = if (mode == ManualSearchMode.Discogs) barcodeQuery else ""
    val hasSearchTerm = hasManualSearchTerm(artistQuery, titleQuery, catalogQuery, effectiveBarcodeQuery, yearQuery)
    val canSearch =
        hasSearchTerm &&
            yearValidationError == null &&
            barcodeValidationError == null &&
            state != ManualSearchUiState.Loading &&
            selectingDiscogsReleaseId == null

    fun runSearch(loadMore: Boolean = false) {
        val artist = artistQuery.trim()
        val title = titleQuery.trim()
        val catalog = catalogQuery.trim()
        val barcode = if (mode == ManualSearchMode.Discogs) barcodeQuery.trim() else ""
        val year = yearQuery.trim().takeIf { it.isNotBlank() }?.toIntOrNull()
        val hasSearchTerm =
            listOf(artist, title, catalog, barcode).any { it.isNotBlank() } || year != null
        if (!hasSearchTerm) {
            state = ManualSearchUiState.Error("Enter at least one search field.")
            return
        }
        if (yearValidationError != null || barcodeValidationError != null) {
            return
        }

        scope.launch {
            val currentResults = (state as? ManualSearchUiState.Success)?.results.orEmpty()
            val offset = if (loadMore) currentResults.size else 0
            retryError = null
            failedImportResult = null
            state =
                if (loadMore && currentResults.isNotEmpty()) {
                    ManualSearchUiState.Success(currentResults, hasMore = true, isLoadingMore = true)
                } else {
                    ManualSearchUiState.Loading
                }
            val page =
                runCatching {
                    when (mode) {
                        ManualSearchMode.Discogs ->
                            apiClient.searchReleases(
                                artist = artist,
                                title = title,
                                catalog = catalog,
                                barcode = barcode,
                                year = year,
                                limit = pageSize,
                                offset = offset,
                            )

                        ManualSearchMode.Collection ->
                            apiClient.searchCollectionReleases(
                                artist = artist,
                                title = title,
                                catalog = catalog,
                                barcode = barcode,
                                year = year,
                                limit = pageSize,
                                offset = offset,
                            )
                    }
                }.getOrElse { error ->
                    if (loadMore && currentResults.isNotEmpty()) {
                        state = ManualSearchUiState.Success(currentResults, hasMore = true)
                        return@launch
                    }
                    retryError = error.toUserMessage(mode.searchErrorMessage)
                    state = ManualSearchUiState.Idle
                    return@launch
                }
            val combinedResults = if (loadMore) currentResults + page.results else page.results
            state =
                if (combinedResults.isEmpty()) {
                    ManualSearchUiState.Empty
                } else {
                    ManualSearchUiState.Success(
                        results = combinedResults,
                        hasMore = page.hasMore,
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
            if (mode == ManualSearchMode.Collection) {
                val releaseId = result.releaseId
                selectingDiscogsReleaseId = null
                if (releaseId == null) {
                    retryError = "Could not open that collection record. Retry."
                    return@launch
                }
                onSelectRecord(releaseId)
                return@launch
            }
            val releaseId =
                runCatching { apiClient.importRelease(result.discogsReleaseId) }
                    .getOrElse { error ->
                        selectingDiscogsReleaseId = null
                        failedImportResult = result
                        retryError = error.toUserMessage("Could not import that record. Retry.")
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
            text = mode.title,
            color = VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
        LocalTimedSessionBanner.current?.let { banner ->
            Spacer(Modifier.height(VinylSpacing.SpaceLg))
            banner()
        }
        retryError?.let { message ->
            Spacer(Modifier.height(VinylSpacing.SpaceLg))
            ErrorRetryCard(
                message = message,
                onRetry = {
                    failedImportResult?.let(::selectResult) ?: runSearch()
                },
            )
        }
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        Column(
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            ManualSearchField(
                label = "Artist",
                placeholder = "Search by artist name",
                value = artistQuery,
                onValueChange = { artistQuery = it.take(MANUAL_SEARCH_TEXT_MAX_CHARS) },
            )
            ManualSearchField(
                label = "Title",
                placeholder = "Search by album title",
                value = titleQuery,
                onValueChange = { titleQuery = it.take(MANUAL_SEARCH_TEXT_MAX_CHARS) },
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
                    onValueChange = { yearQuery = it.digitsOnly(maxLength = RELEASE_YEAR_DIGITS) },
                    modifier = Modifier.weight(1f),
                    error = yearValidationError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
            }
            if (mode == ManualSearchMode.Discogs) {
                ManualSearchField(
                    label = "Barcode",
                    placeholder = "Search by barcode",
                    value = barcodeQuery,
                    onValueChange = { barcodeQuery = it.digitsOnly(maxLength = BARCODE_MAX_DIGITS) },
                    error = barcodeValidationError,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
            }
        }
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        GlassPrimaryButton(
            label = if (state == ManualSearchUiState.Loading) "Searching" else "Search",
            enabled = canSearch,
            onClick = {
                if (canSearch) {
                    focusManager.clearFocus()
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
                ManualSearchUiState.Loading -> ManualSearchMessage(mode.loadingMessage)
                ManualSearchUiState.Empty -> ManualSearchMessage(mode.emptyMessage)
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

enum class ManualSearchMode(
    val title: String,
    val loadingMessage: String,
    val emptyMessage: String,
    val searchErrorMessage: String,
) {
    Discogs(
        title = "Search for your record manually",
        loadingMessage = "Searching Discogs...",
        emptyMessage = "No results found.",
        searchErrorMessage = "Search failed. Retry in a moment.",
    ),
    Collection(
        title = "Search your collection",
        loadingMessage = "Searching collection...",
        emptyMessage = "No collection records found.",
        searchErrorMessage = "Collection search failed. Retry in a moment.",
    ),
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
    val label = if (isLoading) "Loading..." else "Show More"
    Text(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(
                    enabled = !isLoading,
                    onClickLabel = "Show more results",
                    role = Role.Button,
                    onClick = onClick,
                ).padding(vertical = VinylSpacing.SpaceMd),
        text = label,
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
            style = MaterialTheme.typography.titleLarge,
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
    error: String? = null,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
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
                keyboardOptions = keyboardOptions,
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
        error?.let { message ->
            Text(
                text = message,
                color = VinylColors.AccentOrange,
                style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp),
            )
        }
    }
}

private fun String.digitsOnly(maxLength: Int): String = filter(Char::isDigit).take(maxLength)

private fun hasManualSearchTerm(
    artist: String,
    title: String,
    catalog: String,
    barcode: String,
    year: String,
): Boolean = listOf(artist, title, catalog, barcode, year).any { it.trim().isNotEmpty() }

private fun validateReleaseYear(value: String): String? {
    if (value.isBlank()) return null
    if (value.length < RELEASE_YEAR_DIGITS) return "Year must be 4 digits."
    val year = value.toIntOrNull() ?: return "Year must be 4 digits."
    val maxYear = Year.now().value
    return if (year in RELEASE_YEAR_MIN..maxYear) {
        null
    } else {
        "Year must be between $RELEASE_YEAR_MIN and $maxYear."
    }
}

private fun validateBarcode(value: String): String? =
    when {
        value.isBlank() -> null
        value.length !in BARCODE_MIN_DIGITS..BARCODE_MAX_DIGITS ->
            "Barcode must be $BARCODE_MIN_DIGITS-$BARCODE_MAX_DIGITS digits."
        else -> null
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
                    text = record.title,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = if (isSelecting) "Importing..." else record.artist,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = manualSearchResultMetadata(record),
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = record.format ?: "Unknown format",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

private fun manualSearchResultMetadata(record: ReleaseSearchResult): String =
    listOfNotNull(
        record.year?.toString(),
        record.label,
        record.catalogNumber,
    ).joinToString(" • ").ifBlank { "Unknown release info" }
