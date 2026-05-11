package com.example.vinyllistenapp.ui.screens

import androidx.compose.runtime.Composable
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
            records = MockVinylData.records,
            onSelectRecord = {},
            onDismiss = {},
        )
    }
}

@Preview(name = "Placeholder", showBackground = true, backgroundColor = 0xFF101010, widthDp = 390, heightDp = 844)
@Composable
private fun PlaceholderScreenPreview() {
    VinylListenAppTheme {
        PlaceholderScreen(
            title = "Stats",
            message = "Analytics stays out of this prototype pass.",
        )
    }
}
