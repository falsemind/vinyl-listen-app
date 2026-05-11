package com.example.vinyllistenapp.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.example.vinyllistenapp.ui.components.CaptureCircleButton
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import java.io.File

@Composable
fun CaptureRecordScreen(
    onImageSelected: (Uri) -> Unit,
    onManualSearch: () -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    var showCaptureInfo by rememberSaveable { mutableStateOf(false) }
    var pendingCaptureUri by rememberSaveable { mutableStateOf<String?>(null) }
    var permissionDenied by rememberSaveable { mutableStateOf(false) }
    val cameraLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { captured ->
            if (captured) {
                pendingCaptureUri?.let { onImageSelected(Uri.parse(it)) }
            }
        }

    fun launchCameraCapture() {
        val captureUri = createImageCaptureUri(context)
        pendingCaptureUri = captureUri.toString()
        cameraLauncher.launch(captureUri)
    }
    val permissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                permissionDenied = false
                launchCameraCapture()
            } else {
                permissionDenied = true
            }
        }
    val uploadLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            uri?.let(onImageSelected)
        }

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(horizontal = VinylSpacing.SpaceXl),
        ) {
            CaptureHeader(
                onDismiss = onDismiss,
                onInfoClick = { showCaptureInfo = !showCaptureInfo },
            )
            CameraPreviewSurface(
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(vertical = VinylSpacing.SpaceLg),
            )
            GlassPrimaryButton(
                label = "Take Photo",
                onClick = {
                    if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        permissionDenied = false
                        launchCameraCapture()
                    } else {
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    }
                },
            )
            if (permissionDenied) {
                Spacer(Modifier.height(VinylSpacing.SpaceMd))
                Text(
                    modifier = Modifier.fillMaxWidth(),
                    text = "Camera permission is needed to take a photo.",
                    color = VinylColors.AccentOrange,
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Spacer(Modifier.height(VinylSpacing.SpaceLg))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                CaptureSecondaryButton(
                    label = "Upload",
                    accentColor = VinylColors.AccentGreen,
                    onClick = { uploadLauncher.launch("image/*") },
                    modifier = Modifier.weight(1f),
                )
                CaptureSecondaryButton(
                    label = "Manual Search",
                    accentColor = VinylColors.AccentOrange,
                    onClick = onManualSearch,
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.height(VinylSpacing.Space2Xl))
        }
        if (showCaptureInfo) {
            CaptureInfoPopup(onDismiss = { showCaptureInfo = false })
        }
    }
}

private fun createImageCaptureUri(context: Context): Uri {
    val imageFile = File.createTempFile("vinyl_capture_", ".jpg", context.cacheDir)
    return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", imageFile)
}

@Composable
private fun CaptureHeader(
    onDismiss: () -> Unit,
    onInfoClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceSm),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CaptureCircleButton(label = "X", onClick = onDismiss)
        Text(
            text = "Capture Record",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
        CaptureCircleButton(label = "i", onClick = onInfoClick)
    }
}

@Composable
private fun CaptureInfoPopup(onDismiss: () -> Unit) {
    val density = LocalDensity.current

    Popup(
        alignment = Alignment.TopEnd,
        offset =
            IntOffset(
                x = with(density) { (-24).dp.roundToPx() },
                y = with(density) { 96.dp.roundToPx() },
            ),
        onDismissRequest = onDismiss,
        properties = PopupProperties(focusable = true),
    ) {
        Box(
            modifier =
                Modifier
                    .width(280.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                    .padding(VinylSpacing.SpaceLg),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm)) {
                Text(
                    text = "Capture Tips",
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = "Placeholder guidance for barcode, label, and runout capture. Final copy will be updated later.",
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun CameraPreviewSurface(modifier: Modifier = Modifier) {
    val previewBrush =
        Brush.linearGradient(
            listOf(
                VinylColors.SurfaceSecondary,
                VinylColors.SurfacePrimary,
                VinylColors.AccentGreen.copy(alpha = 0.22f),
            ),
        )

    Box(
        modifier =
            modifier
                .clip(VinylShapes.Floating)
                .background(previewBrush)
                .padding(VinylSpacing.SpaceLg),
    ) {
        Box(
            modifier =
                Modifier
                    .align(Alignment.Center)
                    .fillMaxWidth(0.58f)
                    .height(220.dp)
                    .background(VinylColors.AppBackground.copy(alpha = 0.18f), VinylShapes.Card),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier =
                    Modifier
                        .size(96.dp)
                        .background(VinylColors.GreenTint20, CircleShape),
            )
        }
        CaptureHintCard(
            modifier =
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth(),
        )
    }
}

@Composable
private fun CaptureHintCard(modifier: Modifier = Modifier) {
    Box(
        modifier =
            modifier
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary.copy(alpha = 0.95f))
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(horizontal = VinylSpacing.SpaceLg, vertical = VinylSpacing.SpaceMd),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "Capture the record barcode, label, or runout etching",
            color = VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun CaptureSecondaryButton(
    label: String,
    accentColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .height(52.dp)
                .clip(VinylShapes.Button)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                .clickable(
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        CardTopAccentLine(
            accentColor = accentColor,
            alpha = 0.35f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
