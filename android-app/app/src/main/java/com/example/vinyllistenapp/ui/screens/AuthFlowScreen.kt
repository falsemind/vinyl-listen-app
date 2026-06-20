package com.example.vinyllistenapp.ui.screens

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.auth.AuthAccountRepository
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.launch

@Composable
fun AuthFlowScreen(
    authRepository: AuthAccountRepository,
    onAuthenticated: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val coroutineScope = rememberCoroutineScope()
    var mode by rememberSaveable { mutableStateOf(AuthFlowMode.Register) }
    var email by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var verificationEmail by rememberSaveable { mutableStateOf("") }
    var verificationCode by remember { mutableStateOf("") }
    var verificationExpiresAt by rememberSaveable { mutableStateOf<String?>(null) }
    var resetEmail by rememberSaveable { mutableStateOf("") }
    var resetCode by remember { mutableStateOf("") }
    var resetPassword by remember { mutableStateOf("") }
    var resetConfirmPassword by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by rememberSaveable { mutableStateOf<String?>(null) }
    var statusMessage by rememberSaveable { mutableStateOf<String?>(null) }

    fun clearMessages() {
        errorMessage = null
        statusMessage = null
    }

    fun submitRegister() {
        if (isSubmitting || !email.isValidEmail() || password.length < MIN_PASSWORD_LENGTH || password != confirmPassword) return
        val submittedEmail = email.trim()
        val submittedPassword = password
        password = ""
        confirmPassword = ""
        clearMessages()
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
        if (isSubmitting || !email.isValidEmail() || password.isBlank()) return
        val submittedEmail = email.trim()
        val submittedPassword = password
        password = ""
        clearMessages()
        isSubmitting = true
        coroutineScope.launch {
            runCatching { authRepository.signIn(submittedEmail, submittedPassword) }
                .onSuccess { onAuthenticated() }
                .onFailure { error ->
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
                    statusMessage = "Email verified. Sign in to continue."
                }.onFailure { error ->
                    errorMessage = error.authMessage("Code is invalid.")
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
                    password = ""
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
        contentAlignment = Alignment.Center,
    ) {
        Column(
            verticalArrangement = Arrangement.Center,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
        ) {
            AuthFlowHeader(mode)
            Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
            when (mode) {
                AuthFlowMode.Register ->
                    RegisterFields(
                        email = email,
                        password = password,
                        confirmPassword = confirmPassword,
                        isSubmitting = isSubmitting,
                        onEmailChange = { email = it },
                        onPasswordChange = { password = it },
                        onConfirmPasswordChange = { confirmPassword = it },
                        onSubmit = ::submitRegister,
                        onSignIn = {
                            clearMessages()
                            mode = AuthFlowMode.SignIn
                        },
                    )
                AuthFlowMode.Verify ->
                    VerificationFields(
                        email = verificationEmail.ifBlank { email },
                        code = verificationCode,
                        expiresAt = verificationExpiresAt,
                        isSubmitting = isSubmitting,
                        onCodeChange = { verificationCode = it },
                        onSubmit = ::submitVerification,
                        onResend = ::resendVerification,
                        onSignIn = {
                            clearMessages()
                            mode = AuthFlowMode.SignIn
                        },
                    )
                AuthFlowMode.SignIn ->
                    SignInFields(
                        email = email,
                        password = password,
                        isSubmitting = isSubmitting,
                        onEmailChange = { email = it },
                        onPasswordChange = { password = it },
                        onSubmit = ::submitSignIn,
                        onCreateAccount = {
                            clearMessages()
                            mode = AuthFlowMode.Register
                        },
                        onForgotPassword = {
                            clearMessages()
                            mode = AuthFlowMode.ForgotPassword
                        },
                    )
                AuthFlowMode.ForgotPassword ->
                    ForgotPasswordFields(
                        email = email,
                        isSubmitting = isSubmitting,
                        onEmailChange = { email = it },
                        onSubmit = ::submitResetRequest,
                        onBack = {
                            clearMessages()
                            mode = AuthFlowMode.SignIn
                        },
                    )
                AuthFlowMode.ResetPassword ->
                    ResetPasswordFields(
                        email = resetEmail,
                        code = resetCode,
                        password = resetPassword,
                        confirmPassword = resetConfirmPassword,
                        isSubmitting = isSubmitting,
                        onCodeChange = { resetCode = it.toResetCodeInput() },
                        onPasswordChange = { resetPassword = it },
                        onConfirmPasswordChange = { resetConfirmPassword = it },
                        onSubmit = ::submitResetConfirm,
                        onBack = {
                            clearMessages()
                            mode = AuthFlowMode.ForgotPassword
                        },
                    )
            }
            AuthFlowMessages(
                errorMessage = errorMessage,
                statusMessage = statusMessage,
            )
        }
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
    Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
    Button(
        onClick = onSubmit,
        enabled = !isSubmitting && email.isValidEmail() && password.length >= MIN_PASSWORD_LENGTH && password == confirmPassword,
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
            text = "Code expires at $it",
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
}

private fun String.isValidEmail(): Boolean = trim().length >= 3 && "@" in this

private fun String.toResetCodeInput(): String = filter { it.isDigit() }.take(RESET_CODE_LENGTH)

private fun Throwable.authMessage(fallback: String): String = message?.takeIf { it.isNotBlank() } ?: fallback

private const val EMAIL_NOT_VERIFIED = "email_not_verified"
private const val MIN_PASSWORD_LENGTH = 8
private const val RESET_CODE_LENGTH = 6
