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
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.api.toUserMessage
import com.example.vinyllistenapp.data.auth.AuthAccountRepository
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
private const val MIN_ACCOUNT_PASSWORD_LENGTH = 8
private const val RESET_CODE_LENGTH = 6

@Composable
fun SettingsScreen(
    apiClient: VinylApiClient,
    authAccountRepository: AuthAccountRepository? = null,
    message: String,
    onAuthSessionEnded: () -> Unit = {},
    onAccountDeleted: () -> Unit = {},
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
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmNewPassword by remember { mutableStateOf("") }
    var signOutEverywhereOnPasswordChange by rememberSaveable { mutableStateOf(false) }
    var resetCode by remember { mutableStateOf("") }
    var resetPassword by remember { mutableStateOf("") }
    var resetConfirmPassword by remember { mutableStateOf("") }
    var deleteAccountPassword by remember { mutableStateOf("") }
    var accountMessage by remember { mutableStateOf<String?>(null) }
    var accountErrorMessage by remember { mutableStateOf<String?>(null) }
    var isChangingPassword by remember { mutableStateOf(false) }
    var isRequestingReset by remember { mutableStateOf(false) }
    var isConfirmingReset by remember { mutableStateOf(false) }
    var isLoggingOut by remember { mutableStateOf(false) }
    var isLoggingOutEverywhere by remember { mutableStateOf(false) }
    var isDeletingAccount by remember { mutableStateOf(false) }
    var showResetCodeConfirmation by rememberSaveable { mutableStateOf(false) }
    var showLogoutConfirmation by rememberSaveable { mutableStateOf(false) }
    var showLogoutAllConfirmation by rememberSaveable { mutableStateOf(false) }
    var showDeleteAccountConfirmation by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val accountEmail = authAccountRepository?.currentAccountEmail()

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

    fun clearPasswordChangeFields() {
        currentPassword = ""
        newPassword = ""
        confirmNewPassword = ""
    }

    fun clearResetFields() {
        resetCode = ""
        resetPassword = ""
        resetConfirmPassword = ""
    }

    fun changePassword() {
        val repository = authAccountRepository ?: return
        if (
            isChangingPassword ||
            currentPassword.isBlank() ||
            newPassword.length < MIN_ACCOUNT_PASSWORD_LENGTH ||
            newPassword != confirmNewPassword
        ) {
            return
        }
        isChangingPassword = true
        accountMessage = null
        accountErrorMessage = null
        scope.launch {
            runCatching {
                repository.changePassword(
                    currentPassword = currentPassword,
                    newPassword = newPassword,
                    signOutEverywhere = signOutEverywhereOnPasswordChange,
                )
            }.onSuccess { result ->
                clearPasswordChangeFields()
                accountMessage = "Password changed. Revoked sessions: ${result.revokedSessions}."
                if (signOutEverywhereOnPasswordChange) {
                    onAuthSessionEnded()
                }
            }.onFailure { error ->
                accountErrorMessage = error.toUserMessage("Could not change password.")
            }
            isChangingPassword = false
        }
    }

    fun requestPasswordReset() {
        val repository = authAccountRepository ?: return
        if (isRequestingReset) return
        isRequestingReset = true
        accountMessage = null
        accountErrorMessage = null
        scope.launch {
            runCatching { repository.requestCurrentAccountPasswordReset() }
                .onSuccess {
                    accountMessage = "Reset code requested. Check your email."
                }.onFailure { error ->
                    accountErrorMessage = error.toUserMessage("Could not request a reset code.")
                }
            isRequestingReset = false
        }
    }

    fun confirmPasswordReset() {
        val repository = authAccountRepository ?: return
        if (
            isConfirmingReset ||
            resetCode.length != RESET_CODE_LENGTH ||
            resetPassword.length < MIN_ACCOUNT_PASSWORD_LENGTH ||
            resetPassword != resetConfirmPassword
        ) {
            return
        }
        isConfirmingReset = true
        accountMessage = null
        accountErrorMessage = null
        scope.launch {
            runCatching { repository.confirmCurrentAccountPasswordReset(resetCode, resetPassword) }
                .onSuccess {
                    clearResetFields()
                    repository.clearLocalSession()
                    onAuthSessionEnded()
                }.onFailure { error ->
                    accountErrorMessage = error.toUserMessage("Could not reset password.")
                }
            isConfirmingReset = false
        }
    }

    fun logout() {
        val repository = authAccountRepository ?: return
        if (isLoggingOut) return
        isLoggingOut = true
        accountErrorMessage = null
        scope.launch {
            runCatching { repository.logout() }
                .onSuccess { onAuthSessionEnded() }
                .onFailure { onAuthSessionEnded() }
            isLoggingOut = false
        }
    }

    fun logoutAll() {
        val repository = authAccountRepository ?: return
        if (isLoggingOutEverywhere) return
        isLoggingOutEverywhere = true
        accountErrorMessage = null
        scope.launch {
            runCatching { repository.logoutAll() }
                .onSuccess { onAuthSessionEnded() }
                .onFailure { error -> accountErrorMessage = error.toUserMessage("Could not sign out everywhere.") }
            isLoggingOutEverywhere = false
        }
    }

    fun deleteAccount() {
        val repository = authAccountRepository ?: return
        if (isDeletingAccount || deleteAccountPassword.isBlank()) return
        isDeletingAccount = true
        accountErrorMessage = null
        scope.launch {
            runCatching { repository.deleteAccount(deleteAccountPassword) }
                .onSuccess {
                    deleteAccountPassword = ""
                    onAccountDeleted()
                }.onFailure { error ->
                    accountErrorMessage = error.toUserMessage("Could not delete account.")
                }
            isDeletingAccount = false
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
            authAvailable = authAccountRepository != null,
            accountEmail = accountEmail,
            currentPassword = currentPassword,
            newPassword = newPassword,
            confirmNewPassword = confirmNewPassword,
            signOutEverywhereOnPasswordChange = signOutEverywhereOnPasswordChange,
            resetCode = resetCode,
            resetPassword = resetPassword,
            resetConfirmPassword = resetConfirmPassword,
            accountMessage = accountMessage,
            accountErrorMessage = accountErrorMessage,
            isChangingPassword = isChangingPassword,
            isRequestingReset = isRequestingReset,
            isConfirmingReset = isConfirmingReset,
            isLoggingOut = isLoggingOut,
            isLoggingOutEverywhere = isLoggingOutEverywhere,
            isDeletingAccount = isDeletingAccount,
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
            onCurrentPasswordChange = { currentPassword = it },
            onNewPasswordChange = { newPassword = it },
            onConfirmNewPasswordChange = { confirmNewPassword = it },
            onSignOutEverywhereOnPasswordChange = { signOutEverywhereOnPasswordChange = it },
            onChangePassword = ::changePassword,
            onResetCodeChange = { resetCode = it.toResetCodeInput() },
            onResetPasswordChange = { resetPassword = it },
            onResetConfirmPasswordChange = { resetConfirmPassword = it },
            onRequestPasswordReset = { showResetCodeConfirmation = true },
            onConfirmPasswordReset = ::confirmPasswordReset,
            onLogoutClick = { showLogoutConfirmation = true },
            onLogoutAllClick = { showLogoutAllConfirmation = true },
            onDeleteAccountClick = { showDeleteAccountConfirmation = true },
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
    if (showResetCodeConfirmation) {
        AlertDialog(
            onDismissRequest = { showResetCodeConfirmation = false },
            title = { Text("Send reset code") },
            text = {
                Text(
                    "This will send a password reset code to the email address on your account. " +
                        "Confirm to continue.",
                )
            },
            confirmButton = {
                TextButton(
                    enabled = !isRequestingReset,
                    onClick = {
                        showResetCodeConfirmation = false
                        requestPasswordReset()
                    },
                ) {
                    Text("Send code")
                }
            },
            dismissButton = {
                TextButton(onClick = { showResetCodeConfirmation = false }) {
                    Text("Cancel")
                }
            },
        )
    }
    if (showLogoutConfirmation) {
        AlertDialog(
            onDismissRequest = { showLogoutConfirmation = false },
            title = { Text("Log out") },
            text = { Text("You will return to the sign-in screen on this device.") },
            confirmButton = {
                TextButton(
                    enabled = !isLoggingOut,
                    onClick = {
                        showLogoutConfirmation = false
                        logout()
                    },
                ) {
                    Text("Log out")
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutConfirmation = false }) {
                    Text("Cancel")
                }
            },
        )
    }
    if (showLogoutAllConfirmation) {
        AlertDialog(
            onDismissRequest = { showLogoutAllConfirmation = false },
            title = { Text("Sign out everywhere") },
            text = { Text("All active sessions for this account will be revoked, including this device.") },
            confirmButton = {
                TextButton(
                    enabled = !isLoggingOutEverywhere,
                    onClick = {
                        showLogoutAllConfirmation = false
                        logoutAll()
                    },
                ) {
                    Text("Sign out")
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutAllConfirmation = false }) {
                    Text("Cancel")
                }
            },
        )
    }
    if (showDeleteAccountConfirmation) {
        AlertDialog(
            onDismissRequest = { showDeleteAccountConfirmation = false },
            title = { Text("Delete account") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                    Text(
                        "This permanently deletes your account, collection, listening sessions, analytics, " +
                            "insights history, saved provider tokens, and app-owned preferences. " +
                            "This cannot be undone.",
                    )
                    PasswordTextField(
                        value = deleteAccountPassword,
                        onValueChange = { deleteAccountPassword = it },
                        label = "Password",
                        enabled = !isDeletingAccount,
                    )
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !isDeletingAccount && deleteAccountPassword.isNotBlank(),
                    onClick = {
                        showDeleteAccountConfirmation = false
                        deleteAccount()
                    },
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showDeleteAccountConfirmation = false
                        deleteAccountPassword = ""
                    },
                ) {
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
    authAvailable: Boolean,
    accountEmail: String?,
    currentPassword: String,
    newPassword: String,
    confirmNewPassword: String,
    signOutEverywhereOnPasswordChange: Boolean,
    resetCode: String,
    resetPassword: String,
    resetConfirmPassword: String,
    accountMessage: String?,
    accountErrorMessage: String?,
    isChangingPassword: Boolean,
    isRequestingReset: Boolean,
    isConfirmingReset: Boolean,
    isLoggingOut: Boolean,
    isLoggingOutEverywhere: Boolean,
    isDeletingAccount: Boolean,
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
    onCurrentPasswordChange: (String) -> Unit,
    onNewPasswordChange: (String) -> Unit,
    onConfirmNewPasswordChange: (String) -> Unit,
    onSignOutEverywhereOnPasswordChange: (Boolean) -> Unit,
    onChangePassword: () -> Unit,
    onResetCodeChange: (String) -> Unit,
    onResetPasswordChange: (String) -> Unit,
    onResetConfirmPasswordChange: (String) -> Unit,
    onRequestPasswordReset: () -> Unit,
    onConfirmPasswordReset: () -> Unit,
    onLogoutClick: () -> Unit,
    onLogoutAllClick: () -> Unit,
    onDeleteAccountClick: () -> Unit,
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

        SectionTitle("Account management")
        AccountManagementCard(
            authAvailable = authAvailable,
            accountEmail = accountEmail,
            currentPassword = currentPassword,
            newPassword = newPassword,
            confirmNewPassword = confirmNewPassword,
            signOutEverywhereOnPasswordChange = signOutEverywhereOnPasswordChange,
            resetCode = resetCode,
            resetPassword = resetPassword,
            resetConfirmPassword = resetConfirmPassword,
            message = accountMessage,
            errorMessage = accountErrorMessage,
            isChangingPassword = isChangingPassword,
            isRequestingReset = isRequestingReset,
            isConfirmingReset = isConfirmingReset,
            isLoggingOut = isLoggingOut,
            isLoggingOutEverywhere = isLoggingOutEverywhere,
            isDeletingAccount = isDeletingAccount,
            onCurrentPasswordChange = onCurrentPasswordChange,
            onNewPasswordChange = onNewPasswordChange,
            onConfirmNewPasswordChange = onConfirmNewPasswordChange,
            onSignOutEverywhereOnPasswordChange = onSignOutEverywhereOnPasswordChange,
            onChangePassword = onChangePassword,
            onResetCodeChange = onResetCodeChange,
            onResetPasswordChange = onResetPasswordChange,
            onResetConfirmPasswordChange = onResetConfirmPasswordChange,
            onRequestPasswordReset = onRequestPasswordReset,
            onConfirmPasswordReset = onConfirmPasswordReset,
            onLogoutClick = onLogoutClick,
            onLogoutAllClick = onLogoutAllClick,
            onDeleteAccountClick = onDeleteAccountClick,
        )
    }
}

@Composable
private fun AccountManagementCard(
    authAvailable: Boolean,
    accountEmail: String?,
    currentPassword: String,
    newPassword: String,
    confirmNewPassword: String,
    signOutEverywhereOnPasswordChange: Boolean,
    resetCode: String,
    resetPassword: String,
    resetConfirmPassword: String,
    message: String?,
    errorMessage: String?,
    isChangingPassword: Boolean,
    isRequestingReset: Boolean,
    isConfirmingReset: Boolean,
    isLoggingOut: Boolean,
    isLoggingOutEverywhere: Boolean,
    isDeletingAccount: Boolean,
    onCurrentPasswordChange: (String) -> Unit,
    onNewPasswordChange: (String) -> Unit,
    onConfirmNewPasswordChange: (String) -> Unit,
    onSignOutEverywhereOnPasswordChange: (Boolean) -> Unit,
    onChangePassword: () -> Unit,
    onResetCodeChange: (String) -> Unit,
    onResetPasswordChange: (String) -> Unit,
    onResetConfirmPasswordChange: (String) -> Unit,
    onRequestPasswordReset: () -> Unit,
    onConfirmPasswordReset: () -> Unit,
    onLogoutClick: () -> Unit,
    onLogoutAllClick: () -> Unit,
    onDeleteAccountClick: () -> Unit,
) {
    var isPasswordChangeExpanded by rememberSaveable { mutableStateOf(false) }
    var isPasswordResetExpanded by rememberSaveable { mutableStateOf(false) }
    val passwordChangeEnabled =
        authAvailable &&
            !isChangingPassword &&
            currentPassword.isNotBlank() &&
            newPassword.length >= MIN_ACCOUNT_PASSWORD_LENGTH &&
            newPassword == confirmNewPassword
    val passwordResetEnabled =
        authAvailable &&
            !isConfirmingReset &&
            resetCode.length == RESET_CODE_LENGTH &&
            resetPassword.length >= MIN_ACCOUNT_PASSWORD_LENGTH &&
            resetPassword == resetConfirmPassword

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
            accentColor = VinylColors.AccentOrange,
            alpha = 0.30f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceLg)) {
            Text(
                text = accountEmail?.takeIf { it.isNotBlank() } ?: "Signed-in account",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(VinylColors.BorderDefault),
            )
            if (!authAvailable) {
                Text(
                    text = "Account actions are unavailable in preview mode.",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            AccountActionHeader(
                title = "Change password",
                expanded = isPasswordChangeExpanded,
                onClick = { isPasswordChangeExpanded = !isPasswordChangeExpanded },
            )
            if (isPasswordChangeExpanded) {
                Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                    PasswordTextField(
                        value = currentPassword,
                        onValueChange = onCurrentPasswordChange,
                        label = "Current password",
                        enabled = !isChangingPassword,
                    )
                    PasswordTextField(
                        value = newPassword,
                        onValueChange = onNewPasswordChange,
                        label = "New password",
                        enabled = !isChangingPassword,
                    )
                    PasswordTextField(
                        value = confirmNewPassword,
                        onValueChange = onConfirmNewPasswordChange,
                        label = "Confirm new password",
                        enabled = !isChangingPassword,
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            modifier = Modifier.weight(1f).padding(end = VinylSpacing.SpaceMd),
                            text = "Sign out everywhere",
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Switch(
                            checked = signOutEverywhereOnPasswordChange,
                            enabled = !isChangingPassword,
                            onCheckedChange = onSignOutEverywhereOnPasswordChange,
                        )
                    }
                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        enabled = passwordChangeEnabled,
                        shape = VinylShapes.Button,
                        colors =
                            ButtonDefaults.buttonColors(
                                containerColor = VinylColors.AccentGreen,
                                contentColor = VinylColors.TextOnAccent,
                            ),
                        onClick = onChangePassword,
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Edit,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            modifier = Modifier.padding(start = VinylSpacing.SpaceXs),
                            text = if (isChangingPassword) "Saving" else "Save password",
                        )
                    }
                }
            }

            AccountActionHeader(
                title = "Reset with email code",
                expanded = isPasswordResetExpanded,
                onClick = { isPasswordResetExpanded = !isPasswordResetExpanded },
            )
            if (isPasswordResetExpanded) {
                Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd)) {
                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        enabled = authAvailable && !isRequestingReset,
                        shape = VinylShapes.Button,
                        colors =
                            ButtonDefaults.buttonColors(
                                containerColor = VinylColors.SurfaceSecondary,
                                contentColor = VinylColors.TextPrimary,
                            ),
                        onClick = onRequestPasswordReset,
                    ) {
                        Text(if (isRequestingReset) "Sending code" else "Send reset code")
                    }
                    OutlinedTextField(
                        modifier = Modifier.fillMaxWidth(),
                        value = resetCode,
                        onValueChange = onResetCodeChange,
                        enabled = !isConfirmingReset,
                        singleLine = true,
                        label = { Text("Reset code") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    )
                    PasswordTextField(
                        value = resetPassword,
                        onValueChange = onResetPasswordChange,
                        label = "New password",
                        enabled = !isConfirmingReset,
                    )
                    PasswordTextField(
                        value = resetConfirmPassword,
                        onValueChange = onResetConfirmPasswordChange,
                        label = "Confirm new password",
                        enabled = !isConfirmingReset,
                    )
                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        enabled = passwordResetEnabled,
                        shape = VinylShapes.Button,
                        colors =
                            ButtonDefaults.buttonColors(
                                containerColor = VinylColors.AccentGreen,
                                contentColor = VinylColors.TextOnAccent,
                            ),
                        onClick = onConfirmPasswordReset,
                    ) {
                        Text(if (isConfirmingReset) "Resetting" else "Reset password")
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = authAvailable && !isLoggingOut,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.SurfaceSecondary,
                            contentColor = VinylColors.TextPrimary,
                        ),
                    onClick = onLogoutClick,
                ) {
                    Icon(imageVector = Icons.Filled.Close, contentDescription = null, modifier = Modifier.size(18.dp))
                    Text(modifier = Modifier.padding(start = VinylSpacing.SpaceXs), text = if (isLoggingOut) "Logging out" else "Log out")
                }
                Button(
                    modifier = Modifier.weight(1f),
                    enabled = authAvailable && !isLoggingOutEverywhere,
                    shape = VinylShapes.Button,
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = VinylColors.SurfaceSecondary,
                            contentColor = VinylColors.TextSecondary,
                        ),
                    onClick = onLogoutAllClick,
                ) {
                    Text(if (isLoggingOutEverywhere) "Signing out" else "All devices")
                }
            }
            Button(
                modifier = Modifier.fillMaxWidth(),
                enabled = authAvailable && !isDeletingAccount,
                shape = VinylShapes.Button,
                colors =
                    ButtonDefaults.buttonColors(
                        containerColor = VinylColors.SurfaceSecondary,
                        contentColor = VinylColors.AccentOrange,
                    ),
                onClick = onDeleteAccountClick,
            ) {
                Icon(
                    imageVector = Icons.Filled.Delete,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Text(
                    modifier = Modifier.padding(start = VinylSpacing.SpaceXs),
                    text = if (isDeletingAccount) "Deleting" else "Delete account",
                )
            }
            message?.let {
                Text(text = it, color = VinylColors.AccentGreen, style = MaterialTheme.typography.bodyMedium)
            }
            errorMessage?.let {
                Text(text = it, color = VinylColors.AccentOrange, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun AccountActionHeader(
    title: String,
    expanded: Boolean,
    onClick: () -> Unit,
) {
    val arrowRotation by animateFloatAsState(
        targetValue = if (expanded) 180f else -90f,
        animationSpec = tween(durationMillis = 180),
        label = "$title accountActionArrow",
    )
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(
                    onClickLabel = if (expanded) "Collapse $title" else "Expand $title",
                    role = Role.Button,
                    onClick = onClick,
                ),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            modifier = Modifier.weight(1f).padding(end = VinylSpacing.SpaceSm),
            text = title,
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodyLarge,
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
}

@Composable
private fun PasswordTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    enabled: Boolean,
) {
    OutlinedTextField(
        modifier = Modifier.fillMaxWidth(),
        value = value,
        onValueChange = onValueChange,
        enabled = enabled,
        singleLine = true,
        label = { Text(label) },
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
    )
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

private fun String.toResetCodeInput(): String = filter { it.isDigit() }.take(RESET_CODE_LENGTH)
