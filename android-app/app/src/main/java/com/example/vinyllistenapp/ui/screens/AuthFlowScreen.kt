package com.example.vinyllistenapp.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.auth.AuthAccountRepository
import com.example.vinyllistenapp.domain.CollectionSourceOfTruth
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun AuthFlowScreen(
    authRepository: AuthAccountRepository,
    onAuthenticated: () -> Unit,
    modifier: Modifier = Modifier,
    apiClient: VinylApiClient? = null,
    startOnSignIn: Boolean = false,
) {
    val coroutineScope = rememberCoroutineScope()
    var mode by rememberSaveable(startOnSignIn) {
        mutableStateOf(if (startOnSignIn) AuthFlowMode.SignIn else AuthFlowMode.Register)
    }
    var email by rememberSaveable { mutableStateOf("") }
    var registerPassword by remember { mutableStateOf("") }
    var signInPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var verificationEmail by rememberSaveable { mutableStateOf("") }
    var verificationCode by remember { mutableStateOf("") }
    var verificationExpiresAt by rememberSaveable { mutableStateOf<String?>(null) }
    var resetEmail by rememberSaveable { mutableStateOf("") }
    var resetCode by remember { mutableStateOf("") }
    var resetPassword by remember { mutableStateOf("") }
    var resetConfirmPassword by remember { mutableStateOf("") }
    var optionalDiscogsToken by remember { mutableStateOf("") }
    var optionalUseDiscogsSource by rememberSaveable { mutableStateOf(false) }
    var shouldShowOptionalSetupAfterSignIn by rememberSaveable { mutableStateOf(false) }
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by rememberSaveable { mutableStateOf<String?>(null) }
    var statusMessage by rememberSaveable { mutableStateOf<String?>(null) }

    fun clearMessages() {
        errorMessage = null
        statusMessage = null
    }

    fun completeAuthentication() {
        optionalDiscogsToken = ""
        shouldShowOptionalSetupAfterSignIn = false
        onAuthenticated()
    }

    fun submitRegister() {
        if (isSubmitting) return
        clearMessages()
        when {
            !email.isValidEmail() -> {
                errorMessage = "Enter a valid email address."
                return
            }
            !registerPassword.meetsPasswordRequirements() -> {
                errorMessage = PASSWORD_REQUIREMENTS_MESSAGE
                return
            }
            registerPassword != confirmPassword -> {
                errorMessage = "Passwords do not match."
                return
            }
        }
        val submittedEmail = email.trim()
        val submittedPassword = registerPassword
        registerPassword = ""
        confirmPassword = ""
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.register(submittedEmail, submittedPassword) }
                .onSuccess { result ->
                    verificationEmail = result.email
                    verificationExpiresAt = result.verificationExpiresAt
                    verificationCode = ""
                    email = result.email
                    statusMessage = "Verification code sent."
                    mode = AuthFlowMode.Verify
                }.onFailure { error ->
                    errorMessage = error.authMessage("Could not create account.")
                }
            isSubmitting = false
        }
    }

    fun submitSignIn() {
        if (isSubmitting || !email.isValidEmail() || signInPassword.isBlank()) return
        val submittedEmail = email.trim()
        val submittedPassword = signInPassword
        signInPassword = ""
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.signIn(submittedEmail, submittedPassword) }
                .onSuccess {
                    if (shouldShowOptionalSetupAfterSignIn && apiClient != null) {
                        mode = AuthFlowMode.OptionalSetup
                        clearMessages()
                    } else {
                        completeAuthentication()
                    }
                }.onFailure { error ->
                    if ((error as? ApiException)?.code == EMAIL_NOT_VERIFIED) {
                        verificationEmail = submittedEmail
                        verificationCode = ""
                        statusMessage = "Verify your email to continue."
                        mode = AuthFlowMode.Verify
                    } else {
                        errorMessage = error.authMessage("Could not sign in.")
                    }
                }
            isSubmitting = false
        }
    }

    fun submitVerification() {
        val targetEmail = verificationEmail.ifBlank { email }.trim()
        if (isSubmitting || !targetEmail.isValidEmail() || verificationCode.trim().isBlank()) return
        val submittedCode = verificationCode.trim()
        verificationCode = ""
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.verifyEmail(targetEmail, submittedCode) }
                .onSuccess {
                    mode = AuthFlowMode.SignIn
                    email = targetEmail
                    shouldShowOptionalSetupAfterSignIn = true
                    statusMessage = "Email verified. Sign in to continue."
                }.onFailure { error ->
                    errorMessage = error.authMessage("Code is invalid.")
                }
            isSubmitting = false
        }
    }

    fun submitOptionalSetup() {
        val client = apiClient ?: return completeAuthentication()
        val token = optionalDiscogsToken.trim()
        if (isSubmitting || token.isBlank()) return
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching {
                client.saveDiscogsAccessToken(token)
                if (optionalUseDiscogsSource) {
                    client.updateCollectionSettings(CollectionSourceOfTruth.Discogs)
                }
            }.onSuccess {
                completeAuthentication()
            }.onFailure { error ->
                errorMessage = error.authMessage("Could not save optional setup.")
            }
            isSubmitting = false
        }
    }

    fun resendVerification() {
        val targetEmail = verificationEmail.ifBlank { email }.trim()
        if (isSubmitting || !targetEmail.isValidEmail()) return
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.resendVerification(targetEmail) }
                .onSuccess { result ->
                    verificationEmail = result.email
                    verificationExpiresAt = result.verificationExpiresAt
                    verificationCode = ""
                    statusMessage = "New verification code sent."
                }.onFailure { error ->
                    errorMessage = error.authMessage("Could not resend code.")
                }
            isSubmitting = false
        }
    }

    fun submitResetRequest() {
        if (isSubmitting || !email.isValidEmail()) return
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.requestPasswordReset(email) }
                .onSuccess { result ->
                    resetEmail = result.email
                    resetCode = ""
                    resetPassword = ""
                    resetConfirmPassword = ""
                    statusMessage = "If an account exists, a reset code was sent."
                    mode = AuthFlowMode.ResetPassword
                }.onFailure { error ->
                    errorMessage = error.authMessage("Could not request password reset.")
                }
            isSubmitting = false
        }
    }

    fun submitResetConfirm() {
        if (
            isSubmitting ||
            !resetEmail.isValidEmail() ||
            resetCode.length != RESET_CODE_LENGTH ||
            resetPassword.length < MIN_PASSWORD_LENGTH ||
            resetPassword != resetConfirmPassword
        ) {
            return
        }
        val submittedCode = resetCode
        val submittedPassword = resetPassword
        resetCode = ""
        resetPassword = ""
        resetConfirmPassword = ""
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.confirmPasswordReset(resetEmail, submittedCode, submittedPassword) }
                .onSuccess { result ->
                    email = result.email
                    signInPassword = ""
                    statusMessage = "Password updated. Sign in with your new password."
                    mode = AuthFlowMode.SignIn
                }.onFailure { error ->
                    errorMessage = error.authMessage("Could not reset password.")
                }
            isSubmitting = false
        }
    }

    Box(
        modifier =
            modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(VinylSpacing.SpaceXl),
        contentAlignment = if (mode == AuthFlowMode.OptionalSetup) Alignment.TopStart else Alignment.Center,
    ) {
        if (mode == AuthFlowMode.OptionalSetup) {
            OptionalSetupScreen(
                discogsToken = optionalDiscogsToken,
                useDiscogsSource = optionalUseDiscogsSource,
                isSubmitting = isSubmitting,
                errorMessage = errorMessage,
                statusMessage = statusMessage,
                onDiscogsTokenChange = { optionalDiscogsToken = it },
                onUseDiscogsSourceChange = { optionalUseDiscogsSource = it },
                onSubmit = ::submitOptionalSetup,
                onSkip = ::completeAuthentication,
            )
        } else {
            Column(
                verticalArrangement = Arrangement.Center,
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState()),
            ) {
                AuthFlowHeader(mode)
                Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
                AuthFlowFields(
                    mode = mode,
                    email = email,
                    registerPassword = registerPassword,
                    signInPassword = signInPassword,
                    confirmPassword = confirmPassword,
                    verificationEmail = verificationEmail,
                    verificationCode = verificationCode,
                    verificationExpiresAt = verificationExpiresAt,
                    resetEmail = resetEmail,
                    resetCode = resetCode,
                    resetPassword = resetPassword,
                    resetConfirmPassword = resetConfirmPassword,
                    isSubmitting = isSubmitting,
                    onEmailChange = { email = it },
                    onRegisterPasswordChange = { registerPassword = it },
                    onSignInPasswordChange = { signInPassword = it },
                    onConfirmPasswordChange = { confirmPassword = it },
                    onVerificationCodeChange = { verificationCode = it },
                    onResetCodeChange = { resetCode = it.toResetCodeInput() },
                    onResetPasswordChange = { resetPassword = it },
                    onResetConfirmPasswordChange = { resetConfirmPassword = it },
                    onSubmitRegister = ::submitRegister,
                    onSubmitSignIn = ::submitSignIn,
                    onSubmitVerification = ::submitVerification,
                    onResendVerification = ::resendVerification,
                    onSubmitResetRequest = ::submitResetRequest,
                    onSubmitResetConfirm = ::submitResetConfirm,
                    onShowSignIn = {
                        clearMessages()
                        registerPassword = ""
                        confirmPassword = ""
                        mode = AuthFlowMode.SignIn
                    },
                    onShowRegister = {
                        clearMessages()
                        signInPassword = ""
                        mode = AuthFlowMode.Register
                    },
                    onShowForgotPassword = {
                        clearMessages()
                        signInPassword = ""
                        mode = AuthFlowMode.ForgotPassword
                    },
                    onBackToForgotPassword = {
                        clearMessages()
                        mode = AuthFlowMode.ForgotPassword
                    },
                )
                AuthFlowMessages(
                    errorMessage = errorMessage,
                    statusMessage = statusMessage,
                )
            }
        }
    }
}

@Composable
private fun AuthFlowFields(
    mode: AuthFlowMode,
    email: String,
    registerPassword: String,
    signInPassword: String,
    confirmPassword: String,
    verificationEmail: String,
    verificationCode: String,
    verificationExpiresAt: String?,
    resetEmail: String,
    resetCode: String,
    resetPassword: String,
    resetConfirmPassword: String,
    isSubmitting: Boolean,
    onEmailChange: (String) -> Unit,
    onRegisterPasswordChange: (String) -> Unit,
    onSignInPasswordChange: (String) -> Unit,
    onConfirmPasswordChange: (String) -> Unit,
    onVerificationCodeChange: (String) -> Unit,
    onResetCodeChange: (String) -> Unit,
    onResetPasswordChange: (String) -> Unit,
    onResetConfirmPasswordChange: (String) -> Unit,
    onSubmitRegister: () -> Unit,
    onSubmitSignIn: () -> Unit,
    onSubmitVerification: () -> Unit,
    onResendVerification: () -> Unit,
    onSubmitResetRequest: () -> Unit,
    onSubmitResetConfirm: () -> Unit,
    onShowSignIn: () -> Unit,
    onShowRegister: () -> Unit,
    onShowForgotPassword: () -> Unit,
    onBackToForgotPassword: () -> Unit,
) {
    when (mode) {
        AuthFlowMode.Register ->
            RegisterFields(
                email = email,
                password = registerPassword,
                confirmPassword = confirmPassword,
                isSubmitting = isSubmitting,
                onEmailChange = onEmailChange,
                onPasswordChange = onRegisterPasswordChange,
                onConfirmPasswordChange = onConfirmPasswordChange,
                onSubmit = onSubmitRegister,
                onSignIn = onShowSignIn,
            )
        AuthFlowMode.Verify ->
            VerificationFields(
                email = verificationEmail.ifBlank { email },
                code = verificationCode,
                expiresAt = verificationExpiresAt,
                isSubmitting = isSubmitting,
                onCodeChange = onVerificationCodeChange,
                onSubmit = onSubmitVerification,
                onResend = onResendVerification,
                onSignIn = onShowSignIn,
            )
        AuthFlowMode.SignIn ->
            SignInFields(
                email = email,
                password = signInPassword,
                isSubmitting = isSubmitting,
                onEmailChange = onEmailChange,
                onPasswordChange = onSignInPasswordChange,
                onSubmit = onSubmitSignIn,
                onCreateAccount = onShowRegister,
                onForgotPassword = onShowForgotPassword,
            )
        AuthFlowMode.ForgotPassword ->
            ForgotPasswordFields(
                email = email,
                isSubmitting = isSubmitting,
                onEmailChange = onEmailChange,
                onSubmit = onSubmitResetRequest,
                onBack = onShowSignIn,
            )
        AuthFlowMode.ResetPassword ->
            ResetPasswordFields(
                email = resetEmail,
                code = resetCode,
                password = resetPassword,
                confirmPassword = resetConfirmPassword,
                isSubmitting = isSubmitting,
                onCodeChange = onResetCodeChange,
                onPasswordChange = onResetPasswordChange,
                onConfirmPasswordChange = onResetConfirmPasswordChange,
                onSubmit = onSubmitResetConfirm,
                onBack = onBackToForgotPassword,
            )
        AuthFlowMode.OptionalSetup -> Unit
    }
}

@Composable
private fun AuthFlowHeader(mode: AuthFlowMode) {
    Text(
        text =
            when (mode) {
                AuthFlowMode.Register -> "Create account"
                AuthFlowMode.Verify -> "Verify email"
                AuthFlowMode.SignIn -> "Sign in"
                AuthFlowMode.ForgotPassword -> "Reset password"
                AuthFlowMode.ResetPassword -> "Enter reset code"
                AuthFlowMode.OptionalSetup -> "Optional setup"
            },
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.headlineSmall,
        fontWeight = FontWeight.SemiBold,
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceSm))
    Text(
        text =
            when (mode) {
                AuthFlowMode.Register -> "Start with your email and password."
                AuthFlowMode.Verify -> "Enter the code from your email."
                AuthFlowMode.SignIn -> "Use your verified account."
                AuthFlowMode.ForgotPassword -> "Request a reset code."
                AuthFlowMode.ResetPassword -> "Choose a new password."
                AuthFlowMode.OptionalSetup -> "Add Discogs now or skip."
            },
        color = VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodyLarge,
    )
}

@Composable
private fun RegisterFields(
    email: String,
    password: String,
    confirmPassword: String,
    isSubmitting: Boolean,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onConfirmPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onSignIn: () -> Unit,
) {
    AuthEmailField(email, isSubmitting, onEmailChange)
    AuthPasswordField(
        value = password,
        label = "Password",
        enabled = !isSubmitting,
        onValueChange = onPasswordChange,
    )
    AuthPasswordField(
        value = confirmPassword,
        label = "Confirm password",
        enabled = !isSubmitting,
        onValueChange = onConfirmPasswordChange,
    )
    Text(
        text = PASSWORD_REQUIREMENTS_MESSAGE,
        color = VinylColors.TextSecondary,
        style = MaterialTheme.typography.bodySmall,
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled =
            !isSubmitting &&
                email.isValidEmail() &&
                password.meetsPasswordRequirements() &&
                confirmPassword.isNotBlank(),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (isSubmitting) "Creating..." else "Create account")
    }
    TextButton(
        onClick = onSignIn,
        enabled = !isSubmitting,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Sign in")
    }
}

@Composable
private fun VerificationFields(
    email: String,
    code: String,
    expiresAt: String?,
    isSubmitting: Boolean,
    onCodeChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onResend: () -> Unit,
    onSignIn: () -> Unit,
) {
    Text(
        text = email,
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.titleMedium,
    )
    expiresAt?.let {
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceXs))
        Text(
            text = "Code expires at ${it.toLocalExpiryLabel()}",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
    OutlinedTextField(
        value = code,
        onValueChange = onCodeChange,
        enabled = !isSubmitting,
        label = { Text("Verification code") },
        singleLine = true,
        keyboardOptions =
            KeyboardOptions(
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Done,
            ),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled = !isSubmitting && code.trim().isNotBlank(),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (isSubmitting) "Verifying..." else "Verify")
    }
    Row(
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        modifier = Modifier.fillMaxWidth(),
    ) {
        OutlinedButton(
            onClick = onResend,
            enabled = !isSubmitting,
            modifier = Modifier.weight(1f),
        ) {
            Text("Resend")
        }
        TextButton(
            onClick = onSignIn,
            enabled = !isSubmitting,
            modifier = Modifier.weight(1f),
        ) {
            Text("Sign in")
        }
    }
}

@Composable
private fun SignInFields(
    email: String,
    password: String,
    isSubmitting: Boolean,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onCreateAccount: () -> Unit,
    onForgotPassword: () -> Unit,
) {
    AuthEmailField(email, isSubmitting, onEmailChange)
    AuthPasswordField(
        value = password,
        label = "Password",
        enabled = !isSubmitting,
        onValueChange = onPasswordChange,
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled = !isSubmitting && email.isValidEmail() && password.isNotBlank(),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (isSubmitting) "Signing in..." else "Sign in")
    }
    Row(
        horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        modifier = Modifier.fillMaxWidth(),
    ) {
        OutlinedButton(
            onClick = onCreateAccount,
            enabled = !isSubmitting,
            modifier = Modifier.weight(1f),
        ) {
            Text("Create")
        }
        TextButton(
            onClick = onForgotPassword,
            enabled = !isSubmitting,
            modifier = Modifier.weight(1f),
        ) {
            Text("Forgot")
        }
    }
}

@Composable
private fun ForgotPasswordFields(
    email: String,
    isSubmitting: Boolean,
    onEmailChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onBack: () -> Unit,
) {
    AuthEmailField(email, isSubmitting, onEmailChange)
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled = !isSubmitting && email.isValidEmail(),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (isSubmitting) "Sending..." else "Send reset code")
    }
    TextButton(
        onClick = onBack,
        enabled = !isSubmitting,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Back to sign in")
    }
}

@Composable
private fun ResetPasswordFields(
    email: String,
    code: String,
    password: String,
    confirmPassword: String,
    isSubmitting: Boolean,
    onCodeChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onConfirmPasswordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onBack: () -> Unit,
) {
    Text(
        text = email,
        color = VinylColors.TextPrimary,
        style = MaterialTheme.typography.titleMedium,
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
    OutlinedTextField(
        value = code,
        onValueChange = onCodeChange,
        enabled = !isSubmitting,
        label = { Text("Reset code") },
        singleLine = true,
        keyboardOptions =
            KeyboardOptions(
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Next,
            ),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
    AuthPasswordField(
        value = password,
        label = "New password",
        enabled = !isSubmitting,
        onValueChange = onPasswordChange,
    )
    AuthPasswordField(
        value = confirmPassword,
        label = "Confirm new password",
        enabled = !isSubmitting,
        onValueChange = onConfirmPasswordChange,
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled =
            !isSubmitting &&
                code.length == RESET_CODE_LENGTH &&
                password.length >= MIN_PASSWORD_LENGTH &&
                password == confirmPassword,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(if (isSubmitting) "Resetting..." else "Reset password")
    }
    TextButton(
        onClick = onBack,
        enabled = !isSubmitting,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Request a new code")
    }
}

@Composable
private fun OptionalSetupScreen(
    discogsToken: String,
    useDiscogsSource: Boolean,
    isSubmitting: Boolean,
    errorMessage: String?,
    statusMessage: String?,
    onDiscogsTokenChange: (String) -> Unit,
    onUseDiscogsSourceChange: (Boolean) -> Unit,
    onSubmit: () -> Unit,
    onSkip: () -> Unit,
) {
    var privacyExpanded by rememberSaveable { mutableStateOf(false) }

    BackHandler(enabled = !isSubmitting) {
        onSkip()
    }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(top = 48.dp, bottom = VinylSpacing.SpaceLg),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CloseCircleButton(onClick = onSkip)
            Text(
                text = "Optional setup",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.titleLarge,
            )
            Spacer(Modifier.width(40.dp))
        }
        Text(
            text =
                "These optional settings and integrations are highly recommended. " +
                    "They improve the app experience and unlock more advanced collection and discovery features.",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
        Text(
            text = "Discogs Integration",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceSm))
        Text(
            text =
                "Add your Discogs access token to enrich your collection, sync release data, " +
                    "and access more advanced app features.",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
        OutlinedTextField(
            value = discogsToken,
            onValueChange = onDiscogsTokenChange,
            enabled = !isSubmitting,
            label = { Text("Discogs access token") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions =
                KeyboardOptions(
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Done,
                ),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                modifier = Modifier.weight(1f),
                text = "Use Discogs as collection source",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.bodyMedium,
            )
            Switch(
                checked = useDiscogsSource,
                enabled = !isSubmitting && discogsToken.isNotBlank(),
                onCheckedChange = onUseDiscogsSourceChange,
            )
        }
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
        TextButton(
            onClick = { privacyExpanded = !privacyExpanded },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Privacy Notice")
                Icon(
                    imageVector =
                        if (privacyExpanded) {
                            Icons.Filled.KeyboardArrowDown
                        } else {
                            Icons.AutoMirrored.Filled.KeyboardArrowLeft
                        },
                    contentDescription = null,
                )
            }
        }
        if (privacyExpanded) {
            Text(
                modifier = Modifier.padding(horizontal = VinylSpacing.SpaceLg),
                text =
                    "Your token is used to import and sync your Discogs collection, and later your wantlist, " +
                        "plus match records against Discogs release data. The app does not use it to access unrelated " +
                        "Discogs personal data. If you prefer not to use your personal Discogs account, you can create " +
                        "a dedicated account for the app and still benefit from the richer features. Tokens are stored " +
                        "encrypted on the server, and you can revoke access in Discogs or delete the token from the app anytime.",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
        Button(
            onClick = onSubmit,
            enabled = !isSubmitting && discogsToken.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (isSubmitting) "Saving..." else "Save Discogs token")
        }
        AuthFlowMessages(
            errorMessage = errorMessage,
            statusMessage = statusMessage,
        )
        Spacer(modifier = Modifier.height(96.dp))
    }
}

@Composable
private fun AuthEmailField(
    email: String,
    isSubmitting: Boolean,
    onEmailChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = email,
        onValueChange = onEmailChange,
        enabled = !isSubmitting,
        label = { Text("Email") },
        singleLine = true,
        keyboardOptions =
            KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next,
            ),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
}

@Composable
private fun AuthPasswordField(
    value: String,
    label: String,
    enabled: Boolean,
    onValueChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        enabled = enabled,
        label = { Text(label) },
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions =
            KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Next,
            ),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceMd))
}

@Composable
private fun AuthFlowMessages(
    errorMessage: String?,
    statusMessage: String?,
) {
    val message = errorMessage ?: statusMessage ?: return
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Text(
        text = message,
        color = if (errorMessage != null) VinylColors.AccentOrange else VinylColors.AccentGreen,
        style = MaterialTheme.typography.bodyMedium,
    )
}

private enum class AuthFlowMode {
    Register,
    Verify,
    SignIn,
    ForgotPassword,
    ResetPassword,
    OptionalSetup,
}

private fun String.isValidEmail(): Boolean {
    val value = trim()
    val atIndex = value.indexOf('@')
    val dotIndex = value.lastIndexOf('.')
    return atIndex > 0 &&
        dotIndex > atIndex + 1 &&
        dotIndex < value.lastIndex &&
        value.none { it.isWhitespace() } &&
        value.count { it == '@' } == 1
}

private fun String.meetsPasswordRequirements(): Boolean =
    length >= MIN_PASSWORD_LENGTH &&
        any { it.isLetter() } &&
        any { it.isDigit() } &&
        any { !it.isLetterOrDigit() && !it.isWhitespace() }

private fun String.toResetCodeInput(): String = filter { it.isDigit() }.take(RESET_CODE_LENGTH)

private fun String.toLocalExpiryLabel(): String =
    runCatching {
        VERIFICATION_EXPIRY_FORMATTER.format(Instant.parse(this))
    }.getOrElse { this }

private fun Throwable.authMessage(fallback: String): String = message?.takeIf { it.isNotBlank() } ?: fallback

private val VERIFICATION_EXPIRY_FORMATTER: DateTimeFormatter =
    DateTimeFormatter
        .ofPattern("h:mm a, MMM d yyyy", Locale.getDefault())
        .withZone(ZoneId.systemDefault())

private const val EMAIL_NOT_VERIFIED = "email_not_verified"
private const val MIN_PASSWORD_LENGTH = 8
private const val PASSWORD_REQUIREMENTS_MESSAGE =
    "Use 8+ characters with at least one letter, one number, and one symbol."
private const val RESET_CODE_LENGTH = 6
