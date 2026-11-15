package org.fridayuniverse.companion

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * The only Android-sanctioned way for FRIDAY to tap, swipe, type and
 * screenshot: an accessibility service the owner explicitly enables.
 *
 * The service is a pure actuator. It keeps no history, records nothing the
 * owner types himself, and exposes a narrow imperative API to
 * [CommandDispatcher] through [instance].
 */
class FridayAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        instance = this
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        if (instance === this) instance = null
        return super.onUnbind(intent)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    fun tap(x: Int, y: Int): Boolean = gesture(
        Path().apply { moveTo(x.toFloat(), y.toFloat()) }, 60L
    )

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long): Boolean = gesture(
        Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        },
        durationMs.coerceIn(30L, 5_000L)
    )

    private fun gesture(path: Path, durationMs: Long): Boolean {
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
            .build()
        return dispatchGesture(gesture, null, null)
    }

    /** Type into whatever field currently holds input focus. */
    fun typeText(text: String): Boolean {
        val focused = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun pressGlobal(action: Int): Boolean = performGlobalAction(action)

    /** Click the WhatsApp send button in the current window, if present. */
    fun clickWhatsAppSend(): Boolean {
        val root = rootInActiveWindow ?: return false
        val candidates = mutableListOf<AccessibilityNodeInfo>()
        collectByDescription(root, "Send", candidates)
        val button = candidates.firstOrNull { it.isClickable } ?: return false
        return button.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    private fun collectByDescription(
        node: AccessibilityNodeInfo,
        description: String,
        out: MutableList<AccessibilityNodeInfo>
    ) {
        if (node.contentDescription?.toString()?.equals(description, ignoreCase = true) == true) {
            out.add(node)
        }
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectByDescription(it, description, out) }
        }
    }

    /** Screenshot via the accessibility API (Android 11+); returns base64 PNG. */
    suspend fun screenshotBase64(): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        val bitmap = suspendCancellableCoroutine<Bitmap?> { cont ->
            takeScreenshot(
                Display.DEFAULT_DISPLAY,
                mainExecutor,
                object : TakeScreenshotCallback {
                    override fun onSuccess(result: ScreenshotResult) {
                        val hardwareBuffer = result.hardwareBuffer
                        val bmp = Bitmap.wrapHardwareBuffer(hardwareBuffer, result.colorSpace)
                        hardwareBuffer.close()
                        cont.resume(bmp)
                    }

                    override fun onFailure(errorCode: Int) = cont.resume(null)
                }
            )
        } ?: return null
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.PNG, 90, stream)
        return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP)
    }

    companion object {
        @Volatile
        var instance: FridayAccessibilityService? = null
            private set
    }
}
