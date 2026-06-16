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
import androidx.compose.material.icons.filled.Folder
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.CollectionFolder
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.ErrorRetryCard
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun AllDiscogsFoldersScreen(
    apiClient: VinylApiClient,
    onBack: () -> Unit,
    onOpenFolder: (CollectionFolder) -> Unit,
) {
    var folders by remember { mutableStateOf<List<CollectionFolder>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryKey by remember { mutableIntStateOf(0) }
    val scrollState = rememberScrollState()

    LaunchedEffect(retryKey) {
        isLoading = true
        runCatching { apiClient.getCollectionFolders() }
            .onSuccess { page ->
                folders =
                    if (page.discogsConfigured && page.hasExtraFolders) {
                        page.folders.filterNot { it.isDefault }
                    } else {
                        emptyList()
                    }
                error = null
            }.onFailure { failure ->
                folders = emptyList()
                error = failure.toUserMessage("Could not load Discogs folders.")
            }
        isLoading = false
    }

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
            Text(
                modifier = Modifier.weight(1f),
                text = "All Discogs folders",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineLarge,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            CloseCircleButton(onClick = onBack, contentDescription = "Close Discogs folders")
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
        if (!isLoading && error == null && folders.isEmpty()) {
            Text(
                modifier = Modifier.fillMaxWidth(),
                text = "No Discogs folders.",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        folders.forEach { folder ->
            DiscogsFolderCard(
                folder = folder,
                onClick = { onOpenFolder(folder) },
            )
        }
        Spacer(Modifier.height(96.dp))
    }
}

@Composable
private fun DiscogsFolderCard(
    folder: CollectionFolder,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier =
            Modifier.clickable(
                onClickLabel = "Filter collection by ${folder.name}",
                role = Role.Button,
                onClick = onClick,
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
                text = folder.name,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(
                modifier = Modifier.size(40.dp),
                imageVector = Icons.Filled.Folder,
                contentDescription = null,
                tint = VinylColors.AccentGreen,
            )
        }
    }
}
