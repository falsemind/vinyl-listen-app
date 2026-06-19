package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.Canvas
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
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun AuthSplashScreen(
    errorMessage: String?,
    retryCount: Int,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(VinylSpacing.SpaceXl),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier.fillMaxWidth(),
        ) {
            VinylSplashLogo()
            Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
            Text(
                text = "Vinyl Listen",
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(VinylSpacing.Space2Xl))
            if (errorMessage == null) {
                CircularProgressIndicator(color = VinylColors.AccentGreen)
            } else {
                Text(
                    text = errorMessage,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center,
                )
                if (retryCount >= RETRY_HINT_THRESHOLD) {
                    Spacer(modifier = Modifier.height(VinylSpacing.SpaceSm))
                    Text(
                        text = "Check your connection or restart the app if this keeps happening.",
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                    )
                }
                Spacer(modifier = Modifier.height(VinylSpacing.SpaceLg))
                Button(onClick = onRetry) {
                    Text("Retry")
                }
            }
        }
    }
}

@Composable
fun AuthEntryScreen(
    onCreateAccount: () -> Unit,
    onSignIn: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AuthGateActionScreen(
        title = "Account required",
        body = "Create an account or sign in to continue.",
        primaryLabel = "Create account",
        secondaryLabel = "Sign in",
        onPrimary = onCreateAccount,
        onSecondary = onSignIn,
        modifier = modifier,
    )
}

@Composable
fun PasswordReentryRequiredScreen(
    onUseDifferentAccount: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AuthGateActionScreen(
        title = "Password required",
        body = "Enter your password again to continue.",
        primaryLabel = "Enter password",
        secondaryLabel = "Use another account",
        onPrimary = {},
        onSecondary = onUseDifferentAccount,
        modifier = modifier,
    )
}

@Composable
private fun AuthGateActionScreen(
    title: String,
    body: String,
    primaryLabel: String,
    secondaryLabel: String,
    onPrimary: () -> Unit,
    onSecondary: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(VinylSpacing.SpaceXl),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier.fillMaxWidth(),
        ) {
            VinylSplashLogo()
            Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
            Text(
                text = title,
                color = VinylColors.TextPrimary,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(VinylSpacing.SpaceSm))
            Text(
                text = body,
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(VinylSpacing.SpaceXl))
            Row(
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedButton(
                    onClick = onSecondary,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(secondaryLabel)
                }
                Button(
                    onClick = onPrimary,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(primaryLabel)
                }
            }
        }
    }
}

@Composable
private fun VinylSplashLogo(modifier: Modifier = Modifier) {
    val accent = VinylColors.AccentGreen
    Canvas(modifier = modifier.size(84.dp)) {
        drawCircle(color = accent)
        drawCircle(color = VinylColors.AppBackground, radius = size.minDimension * 0.32f)
        drawCircle(color = accent.copy(alpha = 0.65f), radius = size.minDimension * 0.1f)
        drawCircle(color = Color.Black.copy(alpha = 0.35f), radius = size.minDimension * 0.03f)
    }
}

private const val RETRY_HINT_THRESHOLD = 3
