package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.BottomNavBar
import com.example.vinyllistenapp.ui.components.BottomNavItem
import com.example.vinyllistenapp.ui.components.ScreenContent
import com.example.vinyllistenapp.ui.theme.VinylColors

@Composable
fun SettingsScreen(
    message: String,
    onHome: () -> Unit,
    onStats: () -> Unit,
) {
    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Settings", Icons.Filled.Settings, selected = true, onClick = {}),
                    ),
            )
        },
    ) { innerPadding ->
        SettingsContent(message = message, innerPadding = innerPadding)
    }
}

@Composable
private fun SettingsContent(
    message: String,
    innerPadding: PaddingValues = PaddingValues(),
) {
    ScreenContent(title = "Settings", subtitle = message, innerPadding = innerPadding) {
        AccentCard {
            Text(
                text = "Settings placeholder",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}
