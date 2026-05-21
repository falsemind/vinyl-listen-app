package com.example.vinyllistenapp.ui.screens

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.Observer
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.components.InfoCircleButton
import com.example.vinyllistenapp.ui.components.SUCCESS_CONFIRMATION_DELAY_MS
import com.example.vinyllistenapp.ui.components.SuccessStatusFeedback
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import kotlinx.coroutines.delay
import java.io.File
import kotlin.math.max

@Composable
fun CaptureRecordScreen(
    onImageSelected: (Uri) -> Unit,
    onManualSearch: () -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = remember(context) { context.findLifecycleOwner() }
    val mainExecutor = remember(context) { ContextCompat.getMainExecutor(context) }
    var showCaptureInfo by rememberSaveable { mutableStateOf(false) }
    var cameraPermissionGranted by remember { mutableStateOf(context.hasCameraPermission()) }
    var permissionDenied by rememberSaveable { mutableStateOf(false) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var captureError by rememberSaveable { mutableStateOf<String?>(null) }
    var isTakingPhoto by rememberSaveable { mutableStateOf(false) }
    var capturedImageUri by remember { mutableStateOf<String?>(null) }
    var cameraPrivacyBlocked by rememberSaveable { mutableStateOf(false) }
    var cameraRetryAttempt by rememberSaveable { mutableStateOf(0) }
    val photoCaptured = capturedImageUri != null

    LaunchedEffect(capturedImageUri) {
        val uri = capturedImageUri ?: return@LaunchedEffect
        delay(SUCCESS_CONFIRMATION_DELAY_MS)
        onImageSelected(Uri.parse(uri))
    }

    fun refreshCameraPermission(markDenied: Boolean): Boolean {
        val granted = context.hasCameraPermission()
        cameraPermissionGranted = granted
        if (granted) {
            permissionDenied = false
        } else {
            imageCapture = null
            isTakingPhoto = false
            cameraPrivacyBlocked = false
            if (markDenied) permissionDenied = true
        }
        return granted
    }

    fun retryCameraPrivacyAccess(): Boolean {
        if (!refreshCameraPermission(markDenied = true)) return false
        imageCapture = null
        isTakingPhoto = false
        cameraPrivacyBlocked = false
        captureError = null
        cameraRetryAttempt += 1
        return true
    }

    DisposableEffect(context, lifecycleOwner) {
        val owner = lifecycleOwner ?: return@DisposableEffect onDispose {}
        val observer =
            LifecycleEventObserver { _, event ->
                if (event == Lifecycle.Event.ON_RESUME) {
                    if (refreshCameraPermission(markDenied = cameraPermissionGranted || permissionDenied)) {
                        cameraPrivacyBlocked = false
                    }
                }
            }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }

    fun takePhotoInApp() {
        if (photoCaptured) return
        if (!refreshCameraPermission(markDenied = true)) {
            captureError = null
            return
        }
        if (cameraPrivacyBlocked) {
            captureError = CAMERA_PRIVACY_BLOCKED_MESSAGE
            return
        }
        val capture = imageCapture
        if (capture == null) {
            captureError = "Camera is starting. Try again in a moment."
            return
        }

        val imageFile = createImageCaptureFile(context)
        val outputOptions = ImageCapture.OutputFileOptions.Builder(imageFile).build()
        isTakingPhoto = true
        captureError = null
        capture.takePicture(
            outputOptions,
            mainExecutor,
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    isTakingPhoto = false
                    if (imageFile.isLikelyCameraPrivacyPlaceholder()) {
                        imageFile.delete()
                        imageCapture = null
                        cameraPrivacyBlocked = true
                        captureError = CAMERA_PRIVACY_BLOCKED_MESSAGE
                    } else {
                        capturedImageUri = createImageCaptureUri(context, imageFile).toString()
                    }
                }

                override fun onError(exception: ImageCaptureException) {
                    isTakingPhoto = false
                    imageFile.delete()
                    captureError = "Photo could not be captured. Try again."
                }
            },
        )
    }

    val permissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            cameraPermissionGranted = granted
            permissionDenied = !granted
            if (granted) {
                cameraPrivacyBlocked = false
            } else {
                imageCapture = null
                captureError = null
                cameraPrivacyBlocked = false
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
                    .padding(horizontal = VinylSpacing.SpaceMd),
        ) {
            CaptureHeader(
                onDismiss = onDismiss,
                onInfoClick = { showCaptureInfo = !showCaptureInfo },
            )
            CameraPreviewSurface(
                cameraPermissionGranted = cameraPermissionGranted && !cameraPrivacyBlocked,
                photoCaptured = photoCaptured,
                retryAttempt = cameraRetryAttempt,
                onImageCaptureReady = { imageCapture = it },
                onCameraError = { captureError = it },
                onCameraPrivacyBlockedChange = { blocked ->
                    cameraPrivacyBlocked = blocked
                    if (blocked) {
                        imageCapture = null
                        isTakingPhoto = false
                    }
                },
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(vertical = VinylSpacing.SpaceLg),
            )
            GlassPrimaryButton(
                label =
                    when {
                        photoCaptured -> "Photo Captured"
                        isTakingPhoto -> "Taking Photo..."
                        else -> "Take Photo"
                    },
                onClick = {
                    if (!isTakingPhoto && !photoCaptured) {
                        if (cameraPrivacyBlocked) {
                            retryCameraPrivacyAccess()
                        } else if (refreshCameraPermission(markDenied = false)) {
                            takePhotoInApp()
                        } else {
                            permissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    } else {
                        refreshCameraPermission(markDenied = true)
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
            captureError?.let { message ->
                Spacer(Modifier.height(VinylSpacing.SpaceMd))
                Text(
                    modifier = Modifier.fillMaxWidth(),
                    text = message,
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
                    onClick = {
                        if (!isTakingPhoto && !photoCaptured) {
                            uploadLauncher.launch("image/*")
                        }
                    },
                    modifier = Modifier.weight(1f),
                )
                CaptureSecondaryButton(
                    label = "Manual Search",
                    accentColor = VinylColors.AccentOrange,
                    onClick = {
                        if (!isTakingPhoto && !photoCaptured) {
                            onManualSearch()
                        }
                    },
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

private fun createImageCaptureFile(context: Context): File = File.createTempFile("vinyl_capture_", ".jpg", context.cacheDir)

private fun createImageCaptureUri(
    context: Context,
    imageFile: File,
): Uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", imageFile)

private fun Context.hasCameraPermission(): Boolean =
    ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

private const val CAMERA_PRIVACY_BLOCKED_MESSAGE = "Camera access is blocked by system privacy controls."
private const val PRIVACY_PLACEHOLDER_SAMPLE_SIZE = 8
private const val PRIVACY_PLACEHOLDER_MAX_AVERAGE_LUMA = 12
private const val PRIVACY_PLACEHOLDER_MAX_LUMA_RANGE = 8

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }

private fun Context.findLifecycleOwner(): LifecycleOwner? = findActivity() as? LifecycleOwner

private fun File.isLikelyCameraPrivacyPlaceholder(): Boolean {
    val bounds =
        BitmapFactory.Options().apply {
            inJustDecodeBounds = true
        }
    BitmapFactory.decodeFile(path, bounds)
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return false

    val sampleSize =
        generateSequence(1) { it * 2 }
            .first { bounds.outWidth / it <= PRIVACY_PLACEHOLDER_SAMPLE_SIZE && bounds.outHeight / it <= PRIVACY_PLACEHOLDER_SAMPLE_SIZE }
    val bitmap =
        BitmapFactory.decodeFile(
            path,
            BitmapFactory.Options().apply { inSampleSize = max(1, sampleSize) },
        ) ?: return false

    var minLuma = 255
    var maxLuma = 0
    var totalLuma = 0L
    val pixelCount = bitmap.width * bitmap.height
    for (y in 0 until bitmap.height) {
        for (x in 0 until bitmap.width) {
            val pixel = bitmap.getPixel(x, y)
            val luma =
                (
                    0.2126f * android.graphics.Color.red(pixel) +
                        0.7152f * android.graphics.Color.green(pixel) +
                        0.0722f * android.graphics.Color.blue(pixel)
                ).toInt()
            minLuma = minOf(minLuma, luma)
            maxLuma = maxOf(maxLuma, luma)
            totalLuma += luma
        }
    }
    bitmap.recycle()

    val averageLuma = totalLuma / pixelCount
    return averageLuma <= PRIVACY_PLACEHOLDER_MAX_AVERAGE_LUMA &&
        maxLuma - minLuma <= PRIVACY_PLACEHOLDER_MAX_LUMA_RANGE
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
        CloseCircleButton(onClick = onDismiss)
        Text(
            text = "Capture Record",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleLarge,
        )
        InfoCircleButton(onClick = onInfoClick)
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
private fun CameraPreviewSurface(
    cameraPermissionGranted: Boolean,
    photoCaptured: Boolean,
    retryAttempt: Int,
    onImageCaptureReady: (ImageCapture?) -> Unit,
    onCameraError: (String?) -> Unit,
    onCameraPrivacyBlockedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val previewBrush =
        Brush.linearGradient(
            listOf(
                VinylColors.SurfaceSecondary,
                VinylColors.SurfacePrimary,
                VinylColors.AccentGreen.copy(alpha = 0.22f),
            ),
        )

    if (!cameraPermissionGranted) {
        CameraPlaceholderSurface(previewBrush = previewBrush, modifier = modifier)
        return
    }

    val context = LocalContext.current
    val lifecycleOwner = remember(context) { context.findLifecycleOwner() }
    val previewView =
        remember(context) {
            PreviewView(context).apply {
                scaleType = PreviewView.ScaleType.FILL_CENTER
            }
        }

    DisposableEffect(lifecycleOwner, previewView, retryAttempt) {
        val owner = lifecycleOwner
        if (owner == null) {
            onImageCaptureReady(null)
            onCameraError("Camera could not start in this app context.")
            return@DisposableEffect onDispose {}
        }

        onImageCaptureReady(null)
        var disposed = false
        var removeCameraStateObserver: (() -> Unit)? = null
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        val listener =
            Runnable {
                if (disposed) return@Runnable
                runCatching {
                    val cameraProvider = cameraProviderFuture.get()
                    val preview =
                        Preview
                            .Builder()
                            .build()
                            .also { it.setSurfaceProvider(previewView.surfaceProvider) }
                    val imageCapture =
                        ImageCapture
                            .Builder()
                            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                            .build()

                    cameraProvider.unbindAll()
                    val camera =
                        cameraProvider.bindToLifecycle(
                            owner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            imageCapture,
                        )
                    val cameraState = camera.cameraInfo.cameraState
                    val cameraStateObserver =
                        Observer<CameraState> { state ->
                            when {
                                state.error?.code == CameraState.ERROR_CAMERA_DISABLED -> {
                                    onCameraPrivacyBlockedChange(true)
                                    onImageCaptureReady(null)
                                    onCameraError(CAMERA_PRIVACY_BLOCKED_MESSAGE)
                                }

                                state.type == CameraState.Type.OPEN -> {
                                    onCameraPrivacyBlockedChange(false)
                                    onImageCaptureReady(imageCapture)
                                    onCameraError(null)
                                }

                                state.error?.type == CameraState.ErrorType.CRITICAL -> {
                                    onImageCaptureReady(null)
                                    onCameraError("Camera could not start. Check camera access and try again.")
                                }

                                else -> onImageCaptureReady(null)
                            }
                        }
                    cameraState.observe(owner, cameraStateObserver)
                    removeCameraStateObserver = { cameraState.removeObserver(cameraStateObserver) }
                }.onFailure {
                    onImageCaptureReady(null)
                    onCameraError("Camera could not start. Check camera permission and try again.")
                }
            }
        cameraProviderFuture.addListener(listener, ContextCompat.getMainExecutor(context))

        onDispose {
            disposed = true
            removeCameraStateObserver?.invoke()
            onImageCaptureReady(null)
            if (cameraProviderFuture.isDone) {
                runCatching { cameraProviderFuture.get().unbindAll() }
            }
        }
    }

    Box(
        modifier =
            modifier
                .clip(VinylShapes.Floating)
                .background(VinylColors.SurfacePrimary),
    ) {
        AndroidView(
            factory = { previewView },
            modifier = Modifier.matchParentSize(),
        )
        if (photoCaptured) {
            Box(
                modifier =
                    Modifier
                        .matchParentSize()
                        .background(VinylColors.AppBackground.copy(alpha = 0.72f)),
                contentAlignment = Alignment.Center,
            ) {
                SuccessStatusFeedback(message = "Photo captured")
            }
        } else {
            CaptureHintCard(
                modifier =
                    Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth()
                        .padding(VinylSpacing.SpaceLg),
            )
        }
    }
}

@Composable
private fun CameraPlaceholderSurface(
    previewBrush: Brush,
    modifier: Modifier = Modifier,
) {
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
