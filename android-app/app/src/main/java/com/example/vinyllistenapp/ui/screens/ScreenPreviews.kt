package com.example.vinyllistenapp.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.tooling.preview.Preview
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.ui.theme.VinylListenAppTheme

@Preview(name = "Match Confirmation", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun MatchConfirmationScreenPreview() {
    VinylListenAppTheme {
        MatchConfirmationScreen(
            candidates = MockVinylData.matchCandidates,
            apiClient = VinylApiClient(),
            onConfirm = {},
            onManualSearch = {},
            onDismiss = {},
        )
    }
}

@Preview(name = "Manual Search", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun ManualSearchScreenPreview() {
    VinylListenAppTheme {
        ManualSearchScreen(
            apiClient = VinylApiClient(),
            onSelectRecord = {},
            onDismiss = {},
        )
    }
}

@Preview(name = "Settings", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun SettingsScreenPreview() {
    VinylListenAppTheme {
        SettingsScreen(
            message = "Settings stays out of this prototype pass.",
            onHome = {},
            onStats = {},
            onInsights = {},
            onCollection = {},
        )
    }
}

@Preview(name = "Collection", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun CollectionScreenPreview() {
    VinylListenAppTheme {
        CollectionScreen(
            apiClient = VinylApiClient(),
            onHome = {},
            onStats = {},
            onInsights = {},
            onManualSearch = {},
            onOpenRecord = {},
        )
    }
}

@Preview(name = "Analytics", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun AnalyticsScreenPreview() {
    VinylListenAppTheme {
        AnalyticsScreen(
            apiClient = VinylApiClient(),
            onHome = {},
            onOpenRecord = {},
            onInsights = {},
            onCollection = {},
            onViewAllTopRecords = {},
            onViewAllMoods = {},
            onViewAllStyles = {},
            onOpenMonthSessions = {},
            onOpenRatingRecords = {},
            onOpenMoodRecords = {},
            onOpenStyleRecords = {},
        )
    }
}

@Preview(name = "Insights", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun AiInsightsScreenPreview() {
    VinylListenAppTheme {
        AiInsightsScreen(
            apiClient = VinylApiClient(),
            state = rememberAiInsightsScreenState(),
            requestScope = rememberCoroutineScope(),
            onHome = {},
            onStats = {},
            onCollection = {},
        )
    }
}
