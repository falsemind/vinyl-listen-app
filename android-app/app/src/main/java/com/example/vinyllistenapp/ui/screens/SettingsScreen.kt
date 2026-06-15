package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.CollectionSourceOfTruth
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    apiClient: VinylApiClient,
    message: String,
    onHome: () -> Unit,
    onStats: () -> Unit,
    onInsights: () -> Unit,
    onCollection: () -> Unit,
) {
    var sourceOfTruth by remember { mutableStateOf(CollectionSourceOfTruth.App) }
    var isUpdating by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        runCatching { apiClient.getCollectionSettings() }
            .onSuccess {
                sourceOfTruth = it
                errorMessage = null
            }.onFailure { error ->
                errorMessage = error.toUserMessage("Could not load collection settings.")
            }
    }

    fun updateSourceOfTruth(nextSource: CollectionSourceOfTruth) {
        if (isUpdating) return
        val previousSource = sourceOfTruth
        sourceOfTruth = nextSource
        isUpdating = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.updateCollectionSettings(nextSource) }
                .onSuccess { savedSource ->
                    sourceOfTruth = savedSource
                }.onFailure { error ->
                    sourceOfTruth = previousSource
                    errorMessage = error.toUserMessage("Could not update collection settings.")
                }
            isUpdating = false
        }
    }

    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onInsights),
                        BottomNavItem(
                            "Collection",
                            Icons.Filled.LibraryMusic,
                            selected = false,
                            onClick = onCollection,
                        ),
                    ),
            )
        },
    ) { innerPadding ->
        SettingsContent(
            message = message,
            sourceOfTruth = sourceOfTruth,
            isUpdating = isUpdating,
            errorMessage = errorMessage,
            onSourceOfTruthChanged = ::updateSourceOfTruth,
            innerPadding = innerPadding,
        )
    }
}

@Composable
private fun SettingsContent(
    message: String,
    sourceOfTruth: CollectionSourceOfTruth,
    isUpdating: Boolean,
    errorMessage: String?,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
    innerPadding: PaddingValues = PaddingValues(),
) {
    ScreenContent(title = "Settings", subtitle = message, innerPadding = innerPadding) {
        AccentCard {
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
                    text = "Collection source of truth: ${sourceOfTruth.displayName()}",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                )
                Switch(
                    checked = sourceOfTruth == CollectionSourceOfTruth.App,
                    enabled = !isUpdating,
                    onCheckedChange = { checked ->
                        onSourceOfTruthChanged(
                            if (checked) {
                                CollectionSourceOfTruth.App
                            } else {
                                CollectionSourceOfTruth.Discogs
                            },
                        )
                    },
                )
            }
            errorMessage?.let { message ->
                Text(
                    text = message,
                    color = VinylColors.AccentOrange,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

private fun CollectionSourceOfTruth.displayName(): String =
    when (this) {
        CollectionSourceOfTruth.App -> "App"
        CollectionSourceOfTruth.Discogs -> "Discogs"
    }
