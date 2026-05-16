package com.example.vinyllistenapp.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.screens.AnalyticsScreen
import com.example.vinyllistenapp.ui.screens.CaptureRecordScreen
import com.example.vinyllistenapp.ui.screens.HomeScreen
import com.example.vinyllistenapp.ui.screens.ManualSearchScreen
import com.example.vinyllistenapp.ui.screens.MatchConfirmationScreen
import com.example.vinyllistenapp.ui.screens.PlaceholderScreen
import com.example.vinyllistenapp.ui.screens.ProcessingScreen
import com.example.vinyllistenapp.ui.screens.RecentSessionsScreen
import com.example.vinyllistenapp.ui.screens.RecordDetailScreen
import com.example.vinyllistenapp.ui.screens.SessionLoggingScreen
import com.example.vinyllistenapp.ui.screens.TopRecordsScreen

@Composable
fun VinylNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    val apiClient = remember { VinylApiClient() }
    var latestCandidates by remember { mutableStateOf<List<MatchCandidate>>(MockVinylData.matchCandidates) }

    NavHost(
        navController = navController,
        startDestination = VinylRoutes.HOME,
        modifier = modifier,
    ) {
        composable(VinylRoutes.HOME) {
            HomeScreen(
                apiClient = apiClient,
                onLogSession = { navController.navigate(VinylRoutes.CAPTURE_RECORD) },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                onOpenAnalytics = { navController.navigate(VinylRoutes.ANALYTICS) },
                onOpenSettings = { navController.navigate(VinylRoutes.SETTINGS) },
                onViewAllSessions = { navController.navigate(VinylRoutes.RECENT_SESSIONS) },
            )
        }
        composable(VinylRoutes.RECENT_SESSIONS) {
            RecentSessionsScreen(
                apiClient = apiClient,
                onBack = { navController.popBackStack() },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
            )
        }
        composable(VinylRoutes.CAPTURE_RECORD) {
            CaptureRecordScreen(
                onImageSelected = { imageUri -> navController.navigate(VinylRoutes.processing(imageUri)) },
                onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
                onDismiss = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
            )
        }
        composable(
            route = VinylRoutes.PROCESSING_PATTERN,
            arguments =
                listOf(
                    navArgument(VinylRoutes.IMAGE_URI) {
                        type = NavType.StringType
                        nullable = true
                        defaultValue = null
                    },
                ),
        ) { backStackEntry ->
            ProcessingScreen(
                imageUri = backStackEntry.arguments?.getString(VinylRoutes.IMAGE_URI),
                apiClient = apiClient,
                onComplete = { candidates ->
                    latestCandidates = candidates
                    navController.navigate(VinylRoutes.MATCH_CONFIRMATION) {
                        popUpTo(backStackEntry.destination.id) { inclusive = true }
                    }
                },
                onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
            )
        }
        composable(VinylRoutes.MATCH_CONFIRMATION) {
            MatchConfirmationScreen(
                candidates = latestCandidates,
                apiClient = apiClient,
                onConfirm = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
                onDismiss = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
            )
        }
        composable(VinylRoutes.MANUAL_SEARCH) {
            ManualSearchScreen(
                apiClient = apiClient,
                onSelectRecord = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                onDismiss = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
            )
        }
        composable(
            route = VinylRoutes.SESSION_LOGGING_PATTERN,
            arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
        ) { backStackEntry ->
            SessionLoggingScreen(
                releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                apiClient = apiClient,
                onSave = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                onCancel = { navController.popBackStack() },
            )
        }
        composable(
            route = VinylRoutes.RECORD_DETAIL_PATTERN,
            arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
        ) { backStackEntry ->
            RecordDetailScreen(
                releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                apiClient = apiClient,
                onAddSession = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                onHome = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
            )
        }
        composable(VinylRoutes.ANALYTICS) {
            AnalyticsScreen(
                apiClient = apiClient,
                onHome = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                onSettings = { navController.navigate(VinylRoutes.SETTINGS) },
                onViewAllTopRecords = { navController.navigate(VinylRoutes.TOP_RECORDS) },
            )
        }
        composable(VinylRoutes.TOP_RECORDS) {
            TopRecordsScreen(
                apiClient = apiClient,
                onBack = { navController.popBackStack() },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
            )
        }
        composable(VinylRoutes.SETTINGS) {
            PlaceholderScreen(title = "Settings", message = "Settings stays out of this prototype pass.")
        }
    }
}
