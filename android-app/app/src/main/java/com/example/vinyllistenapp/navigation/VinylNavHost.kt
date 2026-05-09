package com.example.vinyllistenapp.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.ui.screens.CaptureRecordScreen
import com.example.vinyllistenapp.ui.screens.HomeScreen
import com.example.vinyllistenapp.ui.screens.ManualSearchScreen
import com.example.vinyllistenapp.ui.screens.MatchConfirmationScreen
import com.example.vinyllistenapp.ui.screens.PlaceholderScreen
import com.example.vinyllistenapp.ui.screens.ProcessingScreen
import com.example.vinyllistenapp.ui.screens.RecordDetailScreen
import com.example.vinyllistenapp.ui.screens.SessionLoggingScreen

@Composable
fun VinylNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    NavHost(
        navController = navController,
        startDestination = VinylRoutes.HOME,
        modifier = modifier,
    ) {
        composable(VinylRoutes.HOME) {
            HomeScreen(
                onLogSession = { navController.navigate(VinylRoutes.CAPTURE_RECORD) },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
            )
        }
        composable(VinylRoutes.CAPTURE_RECORD) {
            CaptureRecordScreen(
                onTakePhoto = { navController.navigate(VinylRoutes.PROCESSING) },
                onUpload = { navController.navigate(VinylRoutes.PROCESSING) },
                onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
            )
        }
        composable(VinylRoutes.PROCESSING) {
            ProcessingScreen(
                onComplete = { navController.navigate(VinylRoutes.MATCH_CONFIRMATION) },
            )
        }
        composable(VinylRoutes.MATCH_CONFIRMATION) {
            MatchConfirmationScreen(
                candidates = MockVinylData.matchCandidates,
                onConfirm = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
            )
        }
        composable(VinylRoutes.MANUAL_SEARCH) {
            ManualSearchScreen(
                records = MockVinylData.records,
                onSelectRecord = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
            )
        }
        composable(
            route = VinylRoutes.SESSION_LOGGING_PATTERN,
            arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
        ) { backStackEntry ->
            SessionLoggingScreen(
                releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
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
                onAddSession = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                onHome = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
            )
        }
        composable(VinylRoutes.ANALYTICS) {
            PlaceholderScreen(title = "Stats", message = "Analytics stays out of this prototype pass.")
        }
        composable(VinylRoutes.SETTINGS) {
            PlaceholderScreen(title = "Settings", message = "Settings stays out of this prototype pass.")
        }
    }
}
