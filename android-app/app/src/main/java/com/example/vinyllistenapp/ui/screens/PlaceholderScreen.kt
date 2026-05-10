package com.example.vinyllistenapp.ui.screens

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.theme.VinylColors

@Composable
fun PlaceholderScreen(
    title: String,
    message: String,
) {
    ScreenContent(title = title, subtitle = message) {
        AccentCard {
            Text(
                text = "Placeholder only",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}
