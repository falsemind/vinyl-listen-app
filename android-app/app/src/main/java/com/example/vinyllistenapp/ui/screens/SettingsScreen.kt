package com.example.vinyllistenapp.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.domain.CollectionSourceOfTruth
import com.example.vinyllistenapp.domain.DiscogsIntegrationStatus
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.components.SectionTitle
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
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
    var integrationStatus by remember { mutableStateOf<DiscogsIntegrationStatus?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var isSavingToken by remember { mutableStateOf(false) }
    var isUpdatingSource by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var tokenInput by rememberSaveable { mutableStateOf("") }
    var tokenEditMode by rememberSaveable { mutableStateOf(false) }
    var showDiscogsConfirmation by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun loadIntegrationStatus() {
        isLoading = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.getDiscogsIntegrationStatus() }
                .onSuccess { status ->
                    integrationStatus = status
                    tokenEditMode = !status.accessTokenSaved
                }.onFailure { error ->
                    errorMessage = error.toUserMessage("Could not load integration settings.")
                }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        loadIntegrationStatus()
    }

    fun saveToken() {
        val token = tokenInput.trim()
        if (token.isBlank() || isSavingToken) return
        isSavingToken = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.saveDiscogsAccessToken(token) }
                .onSuccess { status ->
                    integrationStatus = status
                    tokenInput = ""
                    tokenEditMode = false
                }.onFailure { error ->
                    errorMessage = error.toUserMessage("Could not save Discogs access token.")
                }
            isSavingToken = false
        }
    }

    fun updateSourceOfTruth(nextSource: CollectionSourceOfTruth) {
        if (isUpdatingSource) return
        isUpdatingSource = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.updateCollectionSettings(nextSource) }
                .onSuccess { savedSource ->
                    integrationStatus =
                        (integrationStatus ?: defaultDiscogsIntegrationStatus())
                            .copy(sourceOfTruth = savedSource)
                }.onFailure { error ->
                    errorMessage = error.toUserMessage("Could not update collection settings.")
                }
            isUpdatingSource = false
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
            integrationStatus = integrationStatus,
            isLoading = isLoading,
            isSavingToken = isSavingToken,
            isUpdatingSource = isUpdatingSource,
            tokenInput = tokenInput,
            tokenEditMode = tokenEditMode,
            errorMessage = errorMessage,
            onTokenInputChange = { tokenInput = it },
            onTokenSubmit = ::saveToken,
            onTokenUpdateClick = { tokenEditMode = true },
            onSourceOfTruthChanged = { nextSource ->
                if (nextSource == CollectionSourceOfTruth.Discogs) {
                    showDiscogsConfirmation = true
                } else {
                    updateSourceOfTruth(CollectionSourceOfTruth.App)
                }
            },
            innerPadding = innerPadding,
        )
    }

    if (showDiscogsConfirmation) {
        AlertDialog(
            onDismissRequest = { showDiscogsConfirmation = false },
            title = { Text("Use Discogs as source of truth") },
            text = {
                Text(
                    "Changing source of truth to Discogs may override your active in-app collection. " +
                        "Records not present in your Discogs collection may be removed from the active collection.",
                )
            },
            confirmButton = {
                TextButton(
                    enabled = !isUpdatingSource,
                    onClick = {
                        showDiscogsConfirmation = false
                        updateSourceOfTruth(CollectionSourceOfTruth.Discogs)
                    },
                ) {
                    Text("Confirm")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDiscogsConfirmation = false }) {
                    Text("Cancel")
                }
            },
        )
    }
}

@Composable
private fun SettingsContent(
    message: String,
    integrationStatus: DiscogsIntegrationStatus?,
    isLoading: Boolean,
    isSavingToken: Boolean,
    isUpdatingSource: Boolean,
    tokenInput: String,
    tokenEditMode: Boolean,
    errorMessage: String?,
    onTokenInputChange: (String) -> Unit,
    onTokenSubmit: () -> Unit,
    onTokenUpdateClick: () -> Unit,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
    innerPadding: PaddingValues = PaddingValues(),
) {
    ScreenContent(title = "Settings", subtitle = message, innerPadding = innerPadding) {
        SectionTitle("Integrations")
        DiscogsIntegrationCard(
            status = integrationStatus,
            isLoading = isLoading,
            isSavingToken = isSavingToken,
            isUpdatingSource = isUpdatingSource,
            tokenInput = tokenInput,
            tokenEditMode = tokenEditMode,
            errorMessage = errorMessage,
            onTokenInputChange = onTokenInputChange,
            onTokenSubmit = onTokenSubmit,
            onTokenUpdateClick = onTokenUpdateClick,
            onSourceOfTruthChanged = onSourceOfTruthChanged,
        )
    }
}

@Composable
private fun DiscogsIntegrationCard(
    status: DiscogsIntegrationStatus?,
    isLoading: Boolean,
    isSavingToken: Boolean,
    isUpdatingSource: Boolean,
    tokenInput: String,
    tokenEditMode: Boolean,
    errorMessage: String?,
    onTokenInputChange: (String) -> Unit,
    onTokenSubmit: () -> Unit,
    onTokenUpdateClick: () -> Unit,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(true) }
    val arrowRotation by animateFloatAsState(
        targetValue = if (isExpanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "discogsIntegrationArrow",
    )

    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceLg),
    ) {
        CardTopAccentLine(
            accentColor = VinylColors.AccentGreen,
            alpha = 0.30f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg)) {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .clickable(
                            onClickLabel = if (isExpanded) "Collapse Discogs" else "Expand Discogs",
                            role = Role.Button,
                            onClick = { isExpanded = !isExpanded },
                        ),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    modifier =
                        Modifier
                            .weight(1f)
                            .padding(end = VinylSpacing.SpaceSm),
                    text = "Discogs",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Icon(
                    imageVector = Icons.Filled.KeyboardArrowUp,
                    contentDescription = null,
                    tint = VinylColors.TextSecondary,
                    modifier =
                        Modifier
                            .size(24.dp)
                            .graphicsLayer(rotationZ = arrowRotation),
                )
            }

            if (isExpanded) {
                Spacer(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(1.dp)
                            .background(VinylColors.BorderDefault),
                )
                when {
                    isLoading && status == null -> LoadingIntegrationState()
                    status?.accessTokenSaved == true && !tokenEditMode ->
                        DiscogsTokenSavedState(
                            status = status,
                            isUpdatingSource = isUpdatingSource,
                            onTokenUpdateClick = onTokenUpdateClick,
                            onSourceOfTruthChanged = onSourceOfTruthChanged,
                        )
                    else ->
                        DiscogsTokenInputState(
                            tokenInput = tokenInput,
                            isSavingToken = isSavingToken,
                            onTokenInputChange = onTokenInputChange,
                            onTokenSubmit = onTokenSubmit,
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
}

@Composable
private fun LoadingIntegrationState() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(20.dp),
            color = VinylColors.AccentGreen,
            strokeWidth = 2.dp,
        )
        Text(
            text = "Loading Discogs settings",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun DiscogsTokenInputState(
    tokenInput: String,
    isSavingToken: Boolean,
    onTokenInputChange: (String) -> Unit,
    onTokenSubmit: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = tokenInput,
            onValueChange = onTokenInputChange,
            enabled = !isSavingToken,
            singleLine = true,
            label = { Text("API token") },
            visualTransformation = PasswordVisualTransformation(),
        )
        Button(
            modifier = Modifier.widthIn(min = 120.dp),
            enabled = tokenInput.isNotBlank() && !isSavingToken,
            colors =
                ButtonDefaults.buttonColors(
                    containerColor = VinylColors.AccentGreen,
                    contentColor = VinylColors.TextOnAccent,
                ),
            onClick = onTokenSubmit,
        ) {
            Icon(
                imageVector = Icons.Filled.Add,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Text(
                modifier = Modifier.padding(start = VinylSpacing.SpaceXs),
                text = if (isSavingToken) "Saving" else "Add",
            )
        }
    }
}

@Composable
private fun DiscogsTokenSavedState(
    status: DiscogsIntegrationStatus,
    isUpdatingSource: Boolean,
    onTokenUpdateClick: () -> Unit,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.Check,
                contentDescription = null,
                tint = VinylColors.AccentGreen,
                modifier = Modifier.size(20.dp),
            )
            Text(
                modifier = Modifier.weight(1f),
                text = accessTokenSavedMessage(status),
                color = VinylColors.AccentGreen,
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = onTokenUpdateClick) {
                Text("Update")
            }
        }
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
                text = "Collection source of truth: ${status.sourceOfTruth.displayName()}",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyLarge,
            )
            Switch(
                checked = status.sourceOfTruth == CollectionSourceOfTruth.Discogs,
                enabled = !isUpdatingSource,
                onCheckedChange = { checked ->
                    onSourceOfTruthChanged(
                        if (checked) {
                            CollectionSourceOfTruth.Discogs
                        } else {
                            CollectionSourceOfTruth.App
                        },
                    )
                },
            )
        }
    }
}

private fun defaultDiscogsIntegrationStatus(): DiscogsIntegrationStatus =
    DiscogsIntegrationStatus(
        accessTokenSaved = false,
        externalUserId = null,
        externalUsername = null,
        sourceOfTruth = CollectionSourceOfTruth.App,
        backendIdentifyEnabled = false,
    )

private fun accessTokenSavedMessage(status: DiscogsIntegrationStatus): String =
    status.externalUsername
        ?.takeIf { it.isNotBlank() }
        ?.let { "Access token saved for $it" }
        ?: "Access token saved"

private fun CollectionSourceOfTruth.displayName(): String =
    when (this) {
        CollectionSourceOfTruth.App -> "App"
        CollectionSourceOfTruth.Discogs -> "Discogs"
    }
