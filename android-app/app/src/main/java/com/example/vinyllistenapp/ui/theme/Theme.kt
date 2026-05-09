package com.example.vinyllistenapp.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme =
    darkColorScheme(
        primary = VinylColors.AccentGreen,
        secondary = VinylColors.AccentOrange,
        tertiary = VinylColors.AccentPurple,
        background = VinylColors.AppBackground,
        surface = VinylColors.SurfacePrimary,
        surfaceVariant = VinylColors.SurfaceSecondary,
        onPrimary = VinylColors.TextOnAccent,
        onSecondary = VinylColors.TextOnAccent,
        onTertiary = VinylColors.TextOnAccent,
        onBackground = VinylColors.TextPrimary,
        onSurface = VinylColors.TextPrimary,
        onSurfaceVariant = VinylColors.TextSecondary,
        outline = VinylColors.BorderDefault,
    )

@Composable
fun VinylListenAppTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content,
    )
}
