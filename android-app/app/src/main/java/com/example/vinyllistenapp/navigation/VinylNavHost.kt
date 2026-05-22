package com.example.vinyllistenapp.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.navArgument
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.components.LockPortraitOrientation
import com.example.vinyllistenapp.ui.screens.AnalyticsScreen
import com.example.vinyllistenapp.ui.screens.CaptureRecordScreen
import com.example.vinyllistenapp.ui.screens.HomeScreen
import com.example.vinyllistenapp.ui.screens.ManualSearchScreen
import com.example.vinyllistenapp.ui.screens.MatchConfirmationScreen
import com.example.vinyllistenapp.ui.screens.MoodDistributionScreen
import com.example.vinyllistenapp.ui.screens.ProcessingScreen
import com.example.vinyllistenapp.ui.screens.RecentSessionsScreen
import com.example.vinyllistenapp.ui.screens.RecordDetailScreen
import com.example.vinyllistenapp.ui.screens.SessionLoggingScreen
import com.example.vinyllistenapp.ui.screens.SettingsScreen
import com.example.vinyllistenapp.ui.screens.StyleDistributionScreen
import com.example.vinyllistenapp.ui.screens.TopRecordsScreen

@Composable
fun VinylNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    val apiClient = remember { VinylApiClient() }
    var latestCandidates by rememberSaveable(stateSaver = MatchCandidateListSaver) {
        mutableStateOf(MockVinylData.matchCandidates)
    }
    val backStackEntry by navController.currentBackStackEntryAsState()
    LockPortraitOrientation(enabled = backStackEntry?.destination?.route.isPortraitLockedOverflowRoute())

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
                onDismiss = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
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
                onViewAllMoods = { navController.navigate(VinylRoutes.MOOD_DISTRIBUTION) },
                onViewAllStyles = { navController.navigate(VinylRoutes.STYLE_DISTRIBUTION) },
            )
        }
        composable(VinylRoutes.TOP_RECORDS) {
            TopRecordsScreen(
                apiClient = apiClient,
                onBack = { navController.popBackStack() },
                onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
            )
        }
        composable(VinylRoutes.MOOD_DISTRIBUTION) {
            MoodDistributionScreen(
                apiClient = apiClient,
                onBack = { navController.popBackStack() },
            )
        }
        composable(VinylRoutes.STYLE_DISTRIBUTION) {
            StyleDistributionScreen(
                apiClient = apiClient,
                onBack = { navController.popBackStack() },
            )
        }
        composable(VinylRoutes.SETTINGS) {
            SettingsScreen(
                message = "Settings stays out of this prototype pass.",
                onHome = {
                    navController.navigate(VinylRoutes.HOME) {
                        popUpTo(VinylRoutes.HOME) { inclusive = true }
                    }
                },
                onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
            )
        }
    }
}

private fun String?.isPortraitLockedOverflowRoute(): Boolean =
    this in
        setOf(
            VinylRoutes.CAPTURE_RECORD,
            VinylRoutes.PROCESSING_PATTERN,
            VinylRoutes.MATCH_CONFIRMATION,
            VinylRoutes.MANUAL_SEARCH,
            VinylRoutes.SESSION_LOGGING_PATTERN,
        )

private const val MATCHED_ON_SEPARATOR = "\u001F"

private val MatchCandidateListSaver: Saver<List<MatchCandidate>, List<List<String?>>> =
    Saver(
        save = { candidates -> encodeMatchCandidatesForSavedState(candidates) },
        restore = { value -> decodeMatchCandidatesFromSavedState(value) },
    )

internal fun encodeMatchCandidatesForSavedState(candidates: List<MatchCandidate>): List<List<String?>> =
    candidates.map { candidate ->
        listOf(
            candidate.releaseId,
            candidate.discogsReleaseId.toString(),
            candidate.artist,
            candidate.title,
            candidate.label,
            candidate.confidence.toString(),
            candidate.year?.toString(),
            candidate.catalogNumber,
            candidate.barcode,
            candidate.coverImageUrl,
            candidate.format,
            candidate.matchSource,
            candidate.matchedOn.joinToString(MATCHED_ON_SEPARATOR),
        )
    }

internal fun decodeMatchCandidatesFromSavedState(value: List<List<String?>>): List<MatchCandidate> {
    val decodedCandidates =
        value.mapNotNull { candidate ->
            val discogsReleaseId = candidate.getOrNull(1)?.toLongOrNull() ?: return@mapNotNull null
            MatchCandidate(
                releaseId = candidate.getOrNull(0),
                discogsReleaseId = discogsReleaseId,
                artist = candidate.getOrNull(2) ?: "Unknown artist",
                title = candidate.getOrNull(3) ?: "Unknown title",
                label = candidate.getOrNull(4) ?: "Unknown label",
                confidence = candidate.getOrNull(5)?.toIntOrNull() ?: 0,
                year = candidate.getOrNull(6)?.toIntOrNull(),
                catalogNumber = candidate.getOrNull(7),
                barcode = candidate.getOrNull(8),
                coverImageUrl = candidate.getOrNull(9),
                format = candidate.getOrNull(10),
                matchSource = candidate.getOrNull(11),
                matchedOn =
                    candidate
                        .getOrNull(12)
                        ?.split(MATCHED_ON_SEPARATOR)
                        ?.filter { it.isNotBlank() }
                        .orEmpty(),
            )
        }

    return decodedCandidates.ifEmpty { MockVinylData.matchCandidates }
}
