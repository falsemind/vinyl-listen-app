package com.example.vinyllistenapp.ui.screens

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
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
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.ui.components.CardTopAccentLine
import com.example.vinyllistenapp.ui.components.CloseCircleButton
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.components.InfoCircleButton
import com.example.vinyllistenapp.ui.components.SUCCESS_CONFIRMATION_DELAY_MS
import com.example.vinyllistenapp.ui.components.SuccessStatusFeedback
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.ZoomSuggestionOptions
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.delay
import java.io.File
import java.util.concurrent.Executors
import kotlin.math.abs
import kotlin.math.max

@Composable
fun CaptureRecordScreen(
    apiClient: VinylApiClient,
    onImageSelected: (Uri) -> Unit,
    onManualSearch: () -> Unit,
    onBarcodeDetected: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val hapticFeedback = LocalHapticFeedback.current
    val lifecycleOwner = remember(context) { context.findLifecycleOwner() }
    val mainExecutor = remember(context) { ContextCompat.getMainExecutor(context) }
    val textRecognizer = remember { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    var showCaptureInfo by rememberSaveable { mutableStateOf(false) }
    var showDiscogsTokenInfo by rememberSaveable { mutableStateOf(false) }
    var backendIdentifyEnabled by rememberSaveable { mutableStateOf(false) }
    var cameraPermissionGranted by remember { mutableStateOf(context.hasCameraPermission()) }
    var permissionDenied by rememberSaveable { mutableStateOf(false) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var captureError by rememberSaveable { mutableStateOf<String?>(null) }
    var isTakingPhoto by rememberSaveable { mutableStateOf(false) }
    var isRecognizingText by rememberSaveable { mutableStateOf(false) }
    var barcodeScanMode by rememberSaveable { mutableStateOf(false) }
    var torchEnabled by rememberSaveable { mutableStateOf(false) }
    var capturedImageUri by remember { mutableStateOf<String?>(null) }
    var capturedBarcode by remember { mutableStateOf<String?>(null) }
    var textRecognitionResult by remember { mutableStateOf<TextRecognitionPrototypeResult?>(null) }
    var cameraPrivacyBlocked by rememberSaveable { mutableStateOf(false) }
    var cameraRetryAttempt by rememberSaveable { mutableStateOf(0) }
    val photoCaptured = capturedImageUri != null
    val barcodeCaptured = capturedBarcode != null
    val captureComplete = photoCaptured || barcodeCaptured
    val normalCaptureActionsEnabled = !isTakingPhoto && !isRecognizingText && !captureComplete && !barcodeScanMode
    val photoCaptureActionsEnabled = backendIdentifyEnabled && normalCaptureActionsEnabled
    val textRecognitionActionsEnabled = !isTakingPhoto && !isRecognizingText && !captureComplete && !barcodeScanMode
    LaunchedEffect(Unit) {
        runCatching { apiClient.getDiscogsIntegrationStatus() }
            .onSuccess { status ->
                backendIdentifyEnabled = status.backendIdentifyEnabled
            }
    }
    LaunchedEffect(capturedImageUri) {
        val uri = capturedImageUri ?: return@LaunchedEffect
        delay(SUCCESS_CONFIRMATION_DELAY_MS)
        onImageSelected(Uri.parse(uri))
    }
    LaunchedEffect(capturedBarcode) {
        val barcode = capturedBarcode ?: return@LaunchedEffect
        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
        delay(SUCCESS_CONFIRMATION_DELAY_MS)
        onBarcodeDetected(barcode)
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
    DisposableEffect(textRecognizer) {
        onDispose { textRecognizer.close() }
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

    fun scanTextFromStillFrame() {
        if (!textRecognitionActionsEnabled) return
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
        val startedAtMillis = System.currentTimeMillis()
        isRecognizingText = true
        textRecognitionResult = null
        captureError = null
        capture.takePicture(
            outputOptions,
            mainExecutor,
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    if (imageFile.isLikelyCameraPrivacyPlaceholder()) {
                        imageFile.delete()
                        isRecognizingText = false
                        captureError = "No text found. Make sure the label is visible and well lit."
                        return
                    }

                    val inputImage =
                        runCatching { InputImage.fromFilePath(context, Uri.fromFile(imageFile)) }
                            .getOrElse {
                                imageFile.delete()
                                isRecognizingText = false
                                captureError = "Text could not be read from this photo."
                                return
                            }
                    val imageSizeLabel = imageFile.readImageSizeLabel()
                    textRecognizer
                        .process(inputImage)
                        .addOnSuccessListener(mainExecutor) { recognizedText ->
                            val lines =
                                recognizedText
                                    .textBlocks
                                    .flatMap { block -> block.lines.map { line -> line.text.trim() } }
                                    .filter { it.isNotBlank() }
                            val elapsedMillis = System.currentTimeMillis() - startedAtMillis
                            textRecognitionResult =
                                TextRecognitionPrototypeResult(
                                    lines = lines,
                                    imageSizeLabel = imageSizeLabel,
                                    processingTimeMillis = elapsedMillis,
                                )
                            val linePreview = lines.take(20).joinToString(" | ")
                            Log.d(
                                TEXT_RECOGNITION_TAG,
                                "ML Kit text recognized ${lines.size} lines in ${elapsedMillis}ms " +
                                    "from $imageSizeLabel: $linePreview",
                            )
                            if (lines.isEmpty()) {
                                captureError = "No text found. Try a clearer still frame."
                            }
                        }.addOnFailureListener(mainExecutor) {
                            captureError = "Text recognition failed. Try again."
                        }.addOnCompleteListener(mainExecutor) {
                            isRecognizingText = false
                            imageFile.delete()
                        }
                }

                override fun onError(exception: ImageCaptureException) {
                    isRecognizingText = false
                    imageFile.delete()
                    captureError = "Photo could not be captured for text recognition."
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
                barcodeCaptured = barcodeCaptured,
                retryAttempt = cameraRetryAttempt,
                barcodeScanMode = barcodeScanMode,
                torchEnabled = torchEnabled,
                onImageCaptureReady = { imageCapture = it },
                onBarcodeDetected = { barcode ->
                    barcodeScanMode = false
                    torchEnabled = false
                    capturedBarcode = barcode
                },
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                GlassPrimaryButton(
                    modifier = Modifier.weight(1f),
                    label =
                        when {
                            photoCaptured -> "Photo Captured"
                            barcodeCaptured -> "Barcode Captured"
                            isTakingPhoto -> "Taking Photo..."
                            else -> "Take Photo"
                        },
                    onClick = {
                        if (photoCaptureActionsEnabled) {
                            if (cameraPrivacyBlocked) {
                                retryCameraPrivacyAccess()
                            } else if (refreshCameraPermission(markDenied = false)) {
                                takePhotoInApp()
                            } else {
                                permissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        } else if (!backendIdentifyEnabled) {
                            showDiscogsTokenInfo = true
                        } else if (!barcodeScanMode) {
                            refreshCameraPermission(markDenied = true)
                        }
                    },
                    enabled = photoCaptureActionsEnabled,
                )
                if (!backendIdentifyEnabled) {
                    InfoCircleButton(onClick = { showDiscogsTokenInfo = true })
                }
            }
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
                    label = if (barcodeScanMode) "Cancel Barcode" else "Scan Barcode",
                    accentColor = VinylColors.AccentPurple,
                    onClick = {
                        if (!isTakingPhoto && !isRecognizingText && !captureComplete) {
                            if (barcodeScanMode) {
                                barcodeScanMode = false
                                torchEnabled = false
                                captureError = null
                            } else if (cameraPrivacyBlocked) {
                                retryCameraPrivacyAccess()
                            } else if (refreshCameraPermission(markDenied = false)) {
                                captureError = null
                                textRecognitionResult = null
                                barcodeScanMode = true
                            } else {
                                permissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        }
                    },
                    enabled = !isTakingPhoto && !isRecognizingText && !captureComplete,
                    modifier = Modifier.weight(1f),
                )
                CaptureSecondaryButton(
                    label = if (isRecognizingText) "Reading Text..." else "Scan Text",
                    accentColor = VinylColors.AccentOrange,
                    onClick = {
                        if (cameraPrivacyBlocked) {
                            retryCameraPrivacyAccess()
                        } else if (refreshCameraPermission(markDenied = false)) {
                            scanTextFromStillFrame()
                        } else {
                            permissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    },
                    enabled = textRecognitionActionsEnabled,
                    modifier = Modifier.weight(1f),
                )
            }
            if (barcodeScanMode) {
                Spacer(Modifier.height(VinylSpacing.SpaceMd))
                CaptureSecondaryButton(
                    label = if (torchEnabled) "Torch Off" else "Torch On",
                    accentColor = VinylColors.AccentGreen,
                    onClick = { torchEnabled = !torchEnabled },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            textRecognitionResult?.let { result ->
                Spacer(Modifier.height(VinylSpacing.SpaceMd))
                TextRecognitionPrototypeResultCard(result = result)
            }
            Spacer(Modifier.height(VinylSpacing.SpaceMd))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                CaptureSecondaryButton(
                    label = "Upload",
                    accentColor = VinylColors.AccentGreen,
                    onClick = {
                        if (normalCaptureActionsEnabled) {
                            uploadLauncher.launch("image/*")
                        }
                    },
                    enabled = normalCaptureActionsEnabled,
                    modifier = Modifier.weight(1f),
                )
                CaptureSecondaryButton(
                    label = "Manual Search",
                    accentColor = VinylColors.AccentOrange,
                    onClick = {
                        if (normalCaptureActionsEnabled) {
                            onManualSearch()
                        }
                    },
                    enabled = normalCaptureActionsEnabled,
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.height(VinylSpacing.Space2Xl))
        }
        if (showCaptureInfo) {
            CaptureInfoPopup(onDismiss = { showCaptureInfo = false })
        }
        if (showDiscogsTokenInfo) {
            AlertDialog(
                onDismissRequest = { showDiscogsTokenInfo = false },
                title = { Text("Discogs token required") },
                text = {
                    Text("To enable this feature, please provide your Discogs access token in the app's Integration Settings.")
                },
                confirmButton = {
                    TextButton(onClick = { showDiscogsTokenInfo = false }) {
                        Text("OK")
                    }
                },
            )
        }
    }
}

private fun createImageCaptureFile(context: Context): File = File.createTempFile("vinyl_capture_", ".jpg", context.cacheDir)

private fun createImageCaptureUri(
    context: Context,
    imageFile: File,
): Uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", imageFile)

private data class TextRecognitionPrototypeResult(
    val lines: List<String>,
    val imageSizeLabel: String,
    val processingTimeMillis: Long,
)

private fun File.readImageSizeLabel(): String {
    val options =
        BitmapFactory.Options().apply {
            inJustDecodeBounds = true
        }
    BitmapFactory.decodeFile(absolutePath, options)
    return if (options.outWidth > 0 && options.outHeight > 0) {
        "${options.outWidth}x${options.outHeight}"
    } else {
        "unknown size"
    }
}

private fun Context.hasCameraPermission(): Boolean =
    ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

private const val TEXT_RECOGNITION_TAG = "CaptureTextRecognition"
private const val CAMERA_PRIVACY_BLOCKED_MESSAGE = "Camera access is blocked by system privacy controls."
private const val TEXT_RECOGNITION_RESULT_PREVIEW_LINE_COUNT = 8
private const val PRIVACY_PLACEHOLDER_SAMPLE_SIZE = 8
private const val PRIVACY_PLACEHOLDER_MAX_AVERAGE_LUMA = 12
private const val PRIVACY_PLACEHOLDER_MAX_LUMA_RANGE = 8
private const val BARCODE_STABLE_MILLIS = 900L
private const val MIN_ZOOM_RATIO_DELTA = 0.08f
private const val GUIDE_AREA_HORIZONTAL_MARGIN_FRACTION = 0.08f
private const val GUIDE_AREA_TOP_FRACTION = 0.24f
private const val GUIDE_AREA_BOTTOM_FRACTION = 0.76f

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

private fun normalizeDetectedBarcode(value: String?): String? {
    val digits = value?.filter(Char::isDigit).orEmpty()
    return digits.takeIf { it.length == 8 || it.length == 12 || it.length == 13 }
}

private fun Barcode.isInsideGuideArea(
    imageWidth: Int,
    imageHeight: Int,
): Boolean {
    val box = boundingBox ?: return true
    if (imageWidth <= 0 || imageHeight <= 0) return true
    val centerX = box.centerX().toFloat()
    val centerY = box.centerY().toFloat()
    val minX = imageWidth * GUIDE_AREA_HORIZONTAL_MARGIN_FRACTION
    val maxX = imageWidth * (1f - GUIDE_AREA_HORIZONTAL_MARGIN_FRACTION)
    val minY = imageHeight * GUIDE_AREA_TOP_FRACTION
    val maxY = imageHeight * GUIDE_AREA_BOTTOM_FRACTION
    return centerX in minX..maxX && centerY in minY..maxY
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
    barcodeCaptured: Boolean,
    retryAttempt: Int,
    barcodeScanMode: Boolean,
    torchEnabled: Boolean,
    onImageCaptureReady: (ImageCapture?) -> Unit,
    onBarcodeDetected: (String) -> Unit,
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
    val analyzerExecutor = remember { Executors.newSingleThreadExecutor() }
    val previewView =
        remember(context) {
            PreviewView(context).apply {
                scaleType = PreviewView.ScaleType.FILL_CENTER
            }
        }

    DisposableEffect(analyzerExecutor) {
        onDispose { analyzerExecutor.shutdown() }
    }

    DisposableEffect(lifecycleOwner, previewView, retryAttempt, barcodeScanMode, torchEnabled) {
        val owner = lifecycleOwner
        if (owner == null) {
            onImageCaptureReady(null)
            onCameraError("Camera could not start in this app context.")
            return@DisposableEffect onDispose {}
        }

        onImageCaptureReady(null)
        var disposed = false
        var boundCamera: Camera? = null
        var zoomRequestInFlight = false
        var removeCameraStateObserver: (() -> Unit)? = null
        var analysisInFlight = false
        var acceptedBarcode = false
        var lastBarcode: String? = null
        var stableSinceMillis = 0L
        val barcodeScanner =
            if (barcodeScanMode) {
                val zoomCallback =
                    ZoomSuggestionOptions.ZoomCallback { zoomRatio ->
                        val camera = boundCamera ?: return@ZoomCallback false
                        val zoomState = camera.cameraInfo.zoomState.value
                        val maxZoomRatio = zoomState?.maxZoomRatio ?: zoomRatio
                        val currentZoomRatio = zoomState?.zoomRatio ?: 1f
                        val targetZoomRatio = zoomRatio.coerceIn(1f, maxZoomRatio)
                        if (zoomRequestInFlight || abs(targetZoomRatio - currentZoomRatio) < MIN_ZOOM_RATIO_DELTA) {
                            return@ZoomCallback true
                        }
                        zoomRequestInFlight = true
                        camera.cameraControl
                            .setZoomRatio(targetZoomRatio)
                            .addListener(
                                { zoomRequestInFlight = false },
                                ContextCompat.getMainExecutor(context),
                            )
                        true
                    }
                val options =
                    BarcodeScannerOptions
                        .Builder()
                        .setBarcodeFormats(
                            Barcode.FORMAT_UPC_A,
                            Barcode.FORMAT_UPC_E,
                            Barcode.FORMAT_EAN_13,
                            Barcode.FORMAT_EAN_8,
                        ).setZoomSuggestionOptions(
                            ZoomSuggestionOptions
                                .Builder(zoomCallback)
                                .build(),
                        ).build()
                BarcodeScanning.getClient(options)
            } else {
                null
            }
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
                    val imageAnalysis =
                        if (barcodeScanMode && barcodeScanner != null) {
                            val scanner = barcodeScanner
                            ImageAnalysis
                                .Builder()
                                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                .build()
                                .also { analysis ->
                                    analysis.setAnalyzer(analyzerExecutor) { imageProxy ->
                                        if (analysisInFlight || acceptedBarcode) {
                                            imageProxy.close()
                                            return@setAnalyzer
                                        }
                                        val mediaImage = imageProxy.mediaImageOrNull()
                                        if (mediaImage == null) {
                                            imageProxy.close()
                                            return@setAnalyzer
                                        }

                                        analysisInFlight = true
                                        val inputImage =
                                            InputImage.fromMediaImage(
                                                mediaImage,
                                                imageProxy.imageInfo.rotationDegrees,
                                            )
                                        scanner
                                            .process(inputImage)
                                            .addOnSuccessListener { barcodes ->
                                                val barcode =
                                                    barcodes.firstNotNullOfOrNull { barcode ->
                                                        normalizeDetectedBarcode(barcode.rawValue)
                                                            ?.takeIf {
                                                                barcode.isInsideGuideArea(
                                                                    imageWidth = inputImage.width,
                                                                    imageHeight = inputImage.height,
                                                                )
                                                            }
                                                    }
                                                val nowMillis = System.currentTimeMillis()
                                                if (barcode == null) {
                                                    lastBarcode = null
                                                    stableSinceMillis = 0L
                                                    return@addOnSuccessListener
                                                }
                                                if (barcode != lastBarcode) {
                                                    lastBarcode = barcode
                                                    stableSinceMillis = nowMillis
                                                    return@addOnSuccessListener
                                                }
                                                if (nowMillis - stableSinceMillis >= BARCODE_STABLE_MILLIS) {
                                                    acceptedBarcode = true
                                                    onBarcodeDetected(barcode)
                                                }
                                            }.addOnCompleteListener {
                                                analysisInFlight = false
                                                imageProxy.close()
                                            }
                                    }
                                }
                        } else {
                            null
                        }

                    cameraProvider.unbindAll()
                    val camera =
                        if (imageAnalysis == null) {
                            cameraProvider.bindToLifecycle(
                                owner,
                                CameraSelector.DEFAULT_BACK_CAMERA,
                                preview,
                                imageCapture,
                            )
                        } else {
                            cameraProvider.bindToLifecycle(
                                owner,
                                CameraSelector.DEFAULT_BACK_CAMERA,
                                preview,
                                imageCapture,
                                imageAnalysis,
                            )
                        }
                    boundCamera = camera
                    camera.cameraControl.enableTorch(torchEnabled)
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
            barcodeScanner?.close()
            boundCamera?.cameraControl?.enableTorch(false)
            boundCamera?.cameraControl?.setZoomRatio(1f)
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
        if (photoCaptured || barcodeCaptured) {
            Box(
                modifier =
                    Modifier
                        .matchParentSize()
                        .background(VinylColors.AppBackground.copy(alpha = 0.72f)),
                contentAlignment = Alignment.Center,
            ) {
                SuccessStatusFeedback(message = if (barcodeCaptured) "Barcode captured" else "Photo captured")
            }
        } else if (barcodeScanMode) {
            BarcodeScanGuideOverlay(
                modifier =
                    Modifier
                        .align(Alignment.Center)
                        .fillMaxWidth()
                        .padding(horizontal = VinylSpacing.Space2Xl),
            )
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

@androidx.annotation.OptIn(ExperimentalGetImage::class)
private fun ImageProxy.mediaImageOrNull() = image

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
private fun BarcodeScanGuideOverlay(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(132.dp)
                    .clip(VinylShapes.Card)
                    .border(2.dp, VinylColors.AccentGreen.copy(alpha = 0.86f), VinylShapes.Card)
                    .background(VinylColors.AppBackground.copy(alpha = 0.08f)),
        )
        Spacer(Modifier.height(VinylSpacing.SpaceMd))
        Text(
            text = "Hold still...",
            color = VinylColors.AccentGreen,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleMedium,
        )
    }
}

@Composable
private fun CaptureHintCard(
    modifier: Modifier = Modifier,
    message: String = "Capture the record barcode, label, or runout etching",
) {
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
            text = message,
            color = VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun TextRecognitionPrototypeResultCard(
    result: TextRecognitionPrototypeResult,
    modifier: Modifier = Modifier,
) {
    val previewLines = result.lines.take(TEXT_RECOGNITION_RESULT_PREVIEW_LINE_COUNT)
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .clip(VinylShapes.Card)
                .background(VinylColors.SurfacePrimary.copy(alpha = 0.88f))
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                .padding(VinylSpacing.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Text(
            text = "ML Kit text: ${result.lines.size} lines - ${result.processingTimeMillis}ms - ${result.imageSizeLabel}",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
        )
        if (previewLines.isEmpty()) {
            Text(
                text = "No text lines found.",
                color = VinylColors.TextSecondary,
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            previewLines.forEach { line ->
                Text(
                    text = line,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun CaptureSecondaryButton(
    label: String,
    accentColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier =
            modifier
                .height(52.dp)
                .clip(VinylShapes.Button)
                .background(VinylColors.SurfacePrimary)
                .border(1.dp, VinylColors.BorderDefault, VinylShapes.Button)
                .clickable(
                    enabled = enabled,
                    onClickLabel = label,
                    role = Role.Button,
                    onClick = onClick,
                ),
        contentAlignment = Alignment.Center,
    ) {
        CardTopAccentLine(
            accentColor = accentColor,
            alpha = if (enabled) 0.35f else 0.12f,
            modifier = Modifier.align(Alignment.TopCenter),
        )
        Text(
            text = label,
            color = if (enabled) VinylColors.TextSecondary else VinylColors.TextSecondary.copy(alpha = 0.45f),
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
