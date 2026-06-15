package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.QueryStats
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
fun ManualCollectionEntryScreen(
    onHome: () -> Unit,
    onStats: () -> Unit,
    onInsights: () -> Unit,
    onCollection: () -> Unit,
) {
    Scaffold(
        containerColor = VinylColors.AppBackground,
        bottomBar = {
            BottomNavBar(
                items =
                    listOf(
                        BottomNavItem("Home", Icons.Filled.Home, selected = false, onClick = onHome),
                        BottomNavItem("Stats", Icons.Filled.QueryStats, selected = false, onClick = onStats),
                        BottomNavItem("Insights", Icons.Filled.AutoAwesome, selected = false, onClick = onInsights),
                        BottomNavItem("Collection", Icons.Filled.LibraryMusic, selected = true, onClick = onCollection),
                    ),
            )
        },
    ) { innerPadding ->
        ManualCollectionEntryContent(innerPadding = innerPadding)
    }
}

@Composable
private fun ManualCollectionEntryContent(innerPadding: PaddingValues) {
    ScreenContent(
        title = "Manual Entry",
        subtitle = "Manual release info entry and saving into collection",
        innerPadding = innerPadding,
    ) {
        AccentCard {
            Text(
                text = "Manual release info entry and saving into collection",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}
