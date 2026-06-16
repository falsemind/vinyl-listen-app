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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
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
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val TOKEN_REVEAL_MILLIS = 1_000L

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
    var isDeletingToken by remember { mutableStateOf(false) }
    var isUpdatingSource by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var tokenInput by rememberSaveable { mutableStateOf("") }
    var tokenEditMode by rememberSaveable { mutableStateOf(false) }
    var tokenManageMode by rememberSaveable { mutableStateOf(false) }
    var showDiscogsConfirmation by rememberSaveable { mutableStateOf(false) }
    var showDeleteTokenConfirmation by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun loadIntegrationStatus() {
        isLoading = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.getDiscogsIntegrationStatus() }
                .onSuccess { status ->
                    integrationStatus = status
                    tokenEditMode = false
                    tokenManageMode = false
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
                    tokenManageMode = false
                }.onFailure { error ->
                    errorMessage = error.toUserMessage("Could not save Discogs access token.")
                }
            isSavingToken = false
        }
    }

    fun deleteToken() {
        if (isDeletingToken) return
        isDeletingToken = true
        errorMessage = null
        scope.launch {
            runCatching { apiClient.deleteDiscogsAccessToken() }
                .onSuccess { status ->
                    integrationStatus = status
                    tokenInput = ""
                    tokenEditMode = false
                    tokenManageMode = false
                }.onFailure { error ->
                    errorMessage = error.toUserMessage("Could not delete Discogs access token.")
                }
            isDeletingToken = false
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
            isDeletingToken = isDeletingToken,
            isUpdatingSource = isUpdatingSource,
            tokenInput = tokenInput,
            tokenEditMode = tokenEditMode,
            tokenManageMode = tokenManageMode,
            errorMessage = errorMessage,
            onTokenInputChange = { tokenInput = it },
            onTokenClear = { tokenInput = "" },
            onTokenCancel = {
                tokenInput = ""
                tokenEditMode = false
                tokenManageMode = false
            },
            onTokenSubmit = ::saveToken,
            onTokenManageClick = { tokenManageMode = !tokenManageMode },
            onTokenUpdateClick = {
                tokenManageMode = false
                tokenEditMode = true
            },
            onTokenDeleteClick = { showDeleteTokenConfirmation = true },
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
    if (showDeleteTokenConfirmation) {
        AlertDialog(
            onDismissRequest = { showDeleteTokenConfirmation = false },
            title = { Text("Delete Discogs token") },
            text = {
                Text(
                    "Deleting the token disables Discogs features that require your account " +
                        "and switches collection source of truth back to App.",
                )
            },
            confirmButton = {
                TextButton(
                    enabled = !isDeletingToken,
                    onClick = {
                        showDeleteTokenConfirmation = false
                        deleteToken()
                    },
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteTokenConfirmation = false }) {
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
    isDeletingToken: Boolean,
    isUpdatingSource: Boolean,
    tokenInput: String,
    tokenEditMode: Boolean,
    tokenManageMode: Boolean,
    errorMessage: String?,
    onTokenInputChange: (String) -> Unit,
    onTokenClear: () -> Unit,
    onTokenCancel: () -> Unit,
    onTokenSubmit: () -> Unit,
    onTokenManageClick: () -> Unit,
    onTokenUpdateClick: () -> Unit,
    onTokenDeleteClick: () -> Unit,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
    innerPadding: PaddingValues = PaddingValues(),
) {
    ScreenContent(title = "Settings", subtitle = message, innerPadding = innerPadding) {
        SectionTitle("Integrations")
        DiscogsIntegrationCard(
            status = integrationStatus,
            isLoading = isLoading,
            isSavingToken = isSavingToken,
            isDeletingToken = isDeletingToken,
            isUpdatingSource = isUpdatingSource,
            tokenInput = tokenInput,
            tokenEditMode = tokenEditMode,
            tokenManageMode = tokenManageMode,
            errorMessage = errorMessage,
            onTokenInputChange = onTokenInputChange,
            onTokenClear = onTokenClear,
            onTokenCancel = onTokenCancel,
            onTokenSubmit = onTokenSubmit,
            onTokenManageClick = onTokenManageClick,
            onTokenUpdateClick = onTokenUpdateClick,
            onTokenDeleteClick = onTokenDeleteClick,
            onSourceOfTruthChanged = onSourceOfTruthChanged,
        )
    }
}

@Composable
private fun DiscogsIntegrationCard(
    status: DiscogsIntegrationStatus?,
    isLoading: Boolean,
    isSavingToken: Boolean,
    isDeletingToken: Boolean,
    isUpdatingSource: Boolean,
    tokenInput: String,
    tokenEditMode: Boolean,
    tokenManageMode: Boolean,
    errorMessage: String?,
    onTokenInputChange: (String) -> Unit,
    onTokenClear: () -> Unit,
    onTokenCancel: () -> Unit,
    onTokenSubmit: () -> Unit,
    onTokenManageClick: () -> Unit,
    onTokenUpdateClick: () -> Unit,
    onTokenDeleteClick: () -> Unit,
    onSourceOfTruthChanged: (CollectionSourceOfTruth) -> Unit,
) {
    var isExpanded by rememberSaveable { mutableStateOf(false) }
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
                            tokenManageMode = tokenManageMode,
                            isUpdatingSource = isUpdatingSource,
                            isDeletingToken = isDeletingToken,
                            onTokenManageClick = onTokenManageClick,
                            onTokenUpdateClick = onTokenUpdateClick,
                            onTokenDeleteClick = onTokenDeleteClick,
                            onSourceOfTruthChanged = onSourceOfTruthChanged,
                        )
                    else ->
                        DiscogsTokenInputState(
                            tokenInput = tokenInput,
                            isSavingToken = isSavingToken,
                            onTokenInputChange = onTokenInputChange,
                            onTokenClear = onTokenClear,
                            onTokenCancel = onTokenCancel,
                            onTokenSubmit = onTokenSubmit,
                            showCancel = status?.accessTokenSaved == true || tokenInput.isNotBlank(),
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
    onTokenClear: () -> Unit,
    onTokenCancel: () -> Unit,
    onTokenSubmit: () -> Unit,
    showCancel: Boolean,
) {
    val focusManager = LocalFocusManager.current
    val keyboardController = LocalSoftwareKeyboardController.current
    var revealedIndex by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(tokenInput) {
        revealedIndex =
            if (tokenInput.isNotEmpty()) {
                tokenInput.lastIndex
            } else {
                null
            }
        if (revealedIndex != null) {
            delay(TOKEN_REVEAL_MILLIS)
            revealedIndex = null
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = tokenInput,
            onValueChange = onTokenInputChange,
            enabled = !isSavingToken,
            singleLine = true,
            label = { Text("API token") },
            visualTransformation = TokenRevealVisualTransformation(revealedIndex = revealedIndex),
            trailingIcon = {
                if (tokenInput.isNotBlank()) {
                    Icon(
                        imageVector = Icons.Filled.Close,
                        contentDescription = "Clear token",
                        tint = VinylColors.TextSecondary,
                        modifier =
                            Modifier
                                .size(22.dp)
                                .clip(VinylShapes.Chip)
                                .clickable(
                                    onClickLabel = "Clear token",
                                    role = Role.Button,
                                    onClick = onTokenClear,
                                ).padding(VinylSpacing.SpaceXs),
                    )
                }
            },
        )
        if (showCancel || tokenInput.isNotBlank()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = !isSavingToken,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.SurfaceSecondary,
                            contentColor = VinylColors.TextSecondary,
                        ),
                    onClick = {
                        onTokenCancel()
                        focusManager.clearFocus(force = true)
                        keyboardController?.hide()
                    },
                ) {
                    Text("Cancel")
                }
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = tokenInput.isNotBlank() && !isSavingToken,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.AccentGreen,
                            contentColor = VinylColors.TextOnAccent,
                        ),
                    onClick = onTokenSubmit,
                ) {
                    Text(if (isSavingToken) "Saving" else "Upload Token")
                }
            }
        }
    }
}

private class TokenRevealVisualTransformation(
    private val revealedIndex: Int?,
) : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText {
        val maskedText =
            buildString {
                text.text.forEachIndexed { index, character ->
                    append(
                        if (index == revealedIndex) {
                            character
                        } else {
                            '\u2022'
                        },
                    )
                }
            }

        return TransformedText(
            text = AnnotatedString(maskedText),
            offsetMapping = OffsetMapping.Identity,
        )
    }
}

@Composable
private fun DiscogsTokenSavedState(
    status: DiscogsIntegrationStatus,
    tokenManageMode: Boolean,
    isUpdatingSource: Boolean,
    isDeletingToken: Boolean,
    onTokenManageClick: () -> Unit,
    onTokenUpdateClick: () -> Unit,
    onTokenDeleteClick: () -> Unit,
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
            AccessTokenSavedLabel(
                modifier = Modifier.weight(1f),
                username = status.externalUsername,
            )
            Icon(
                imageVector = if (tokenManageMode) Icons.Filled.Close else Icons.Filled.Edit,
                contentDescription =
                    if (tokenManageMode) {
                        "Close Discogs token actions"
                    } else {
                        "Manage Discogs token"
                    },
                tint = VinylColors.AccentGreen,
                modifier =
                    Modifier
                        .size(32.dp)
                        .clip(VinylShapes.Chip)
                        .clickable(
                            onClickLabel =
                                if (tokenManageMode) {
                                    "Close Discogs token actions"
                                } else {
                                    "Manage Discogs token"
                                },
                            role = Role.Button,
                            onClick = onTokenManageClick,
                        ).padding(VinylSpacing.SpaceXs),
            )
        }
        if (tokenManageMode) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = !isDeletingToken,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.AccentGreen,
                            contentColor = VinylColors.TextOnAccent,
                        ),
                    onClick = onTokenUpdateClick,
                ) {
                    Text("Update")
                }
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = !isDeletingToken,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.SurfaceSecondary,
                            contentColor = VinylColors.AccentOrange,
                        ),
                    onClick = onTokenDeleteClick,
                ) {
                    Icon(
                        imageVector = Icons.Filled.Delete,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        modifier = Modifier.padding(start = VinylSpacing.SpaceXs),
                        text = if (isDeletingToken) "Deleting" else "Delete",
                    )
                }
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
                checked = status.sourceOfTruth == CollectionSourceOfTruth.App,
                enabled = !isUpdatingSource,
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
    }
}

@Composable
private fun AccessTokenSavedLabel(
    username: String?,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "Access token saved for",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        username?.takeIf { it.isNotBlank() }?.let { name ->
            Text(
                modifier =
                    Modifier
                        .clip(VinylShapes.Chip)
                        .background(VinylColors.GreenTint20)
                        .border(1.dp, VinylColors.AccentGreen, VinylShapes.Chip)
                        .padding(horizontal = VinylSpacing.SpaceSm, vertical = VinylSpacing.SpaceXs),
                text = name,
                color = VinylColors.AccentGreen,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
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

private fun CollectionSourceOfTruth.displayName(): String =
    when (this) {
        CollectionSourceOfTruth.App -> "App"
        CollectionSourceOfTruth.Discogs -> "Discogs"
    }
