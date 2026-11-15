package org.fridayuniverse.companion

import android.accessibilityservice.AccessibilityService
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.media.RingtoneManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.provider.AlarmClock
import android.telephony.SmsManager
import android.view.KeyEvent
import java.net.URLEncoder
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject

/** Result of one command: mirrors the bridge evidence fields. */
data class CommandResult(val ok: Boolean, val output: Any?, val error: String?)

/**
 * Maps every allowlisted phone-bridge command to real Android APIs.
 *
 * Capability honesty is enforced twice: the hello frame advertises only
 * what is usable *right now* (see [advertisedCapabilities]), and each
 * handler re-checks its prerequisite at execution time and returns a
 * precise error instead of a fake success.
 */
class CommandDispatcher(private val context: Context) {

    fun advertisedCapabilities(): List<String> {
        val caps = BASE_CAPABILITIES.toMutableList()
        if (FridayAccessibilityService.instance != null) caps += ACCESSIBILITY_CAPABILITIES
        if (FridayNotificationListener.instance != null) caps += "read_notifications"
        return caps
    }

    suspend fun execute(command: String, args: JSONObject): CommandResult = try {
        when (command) {
            "device_status" -> deviceStatus()
            "open_app" -> openApp(args.getString("app"))
            "close_app" -> closeApp(args.getString("app"))
            "open_url" -> openUrl(args.getString("url"))
            "make_call" -> makeCall(args.getString("number"))
            "send_sms" -> sendSms(args.getString("number"), args.getString("message"))
            "send_whatsapp" -> sendWhatsApp(args.getString("number"), args.getString("message"))
            "read_notifications" -> readNotifications(args.optInt("limit", 20))
            "set_alarm" -> setAlarm(args.getInt("hour"), args.getInt("minute"), args.optString("label", ""))
            "media_control" -> mediaControl(args.getString("action"))
            "set_volume" -> setVolume(args.getInt("percent"), args.optString("stream", "music"))
            "find_phone" -> findPhone(args.optInt("seconds", 30))
            "tap" -> withAccessibility("tap") { it.tap(args.getInt("x"), args.getInt("y")) }
            "swipe" -> withAccessibility("swipe") {
                it.swipe(
                    args.getInt("x1"), args.getInt("y1"),
                    args.getInt("x2"), args.getInt("y2"),
                    args.optLong("duration_ms", 300)
                )
            }
            "type_text" -> withAccessibility("type_text") { it.typeText(args.getString("text")) }
            "press_key" -> pressKey(args.getString("key"))
            "screenshot" -> screenshot()
            else -> CommandResult(false, null, "companion app does not implement '$command'")
        }
    } catch (e: Exception) {
        CommandResult(false, null, "${e.javaClass.simpleName}: ${e.message}")
    }

    // ------------------------------------------------------------------

    private fun deviceStatus(): CommandResult {
        val battery = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val info = JSONObject()
            .put("model", Build.MODEL)
            .put("manufacturer", Build.MANUFACTURER)
            .put("android_version", Build.VERSION.RELEASE)
            .put("battery_percent", level)
            .put("accessibility_enabled", FridayAccessibilityService.instance != null)
            .put("notification_access_enabled", FridayNotificationListener.instance != null)
        return CommandResult(true, info.toString(), null)
    }

    private fun packageFor(app: String): String =
        APP_PACKAGES[app.trim().lowercase()] ?: app.trim()

    private fun openApp(app: String): CommandResult {
        val pkg = packageFor(app)
        val intent = context.packageManager.getLaunchIntentForPackage(pkg)
            ?: return CommandResult(false, null, "no launchable app for '$app' (package $pkg)")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return CommandResult(true, "launched $pkg", null)
    }

    private fun closeApp(app: String): CommandResult {
        // Android lets an app kill *background* processes of another package
        // with KILL_BACKGROUND_PROCESSES; a foreground app can only be left,
        // not force-stopped, without system privileges. Say so in the result.
        val pkg = packageFor(app)
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        am.killBackgroundProcesses(pkg)
        return CommandResult(true, "background processes of $pkg killed (a foreground app cannot be force-stopped by another app)", null)
    }

    private fun openUrl(url: String): CommandResult {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return CommandResult(true, "opened $url", null)
    }

    private fun makeCall(number: String): CommandResult {
        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return CommandResult(true, "calling $number", null)
    }

    private fun sendSms(number: String, message: String): CommandResult {
        @Suppress("DEPRECATION")
        val sms = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(SmsManager::class.java)
        } else {
            SmsManager.getDefault()
        }
        sms.sendTextMessage(number, null, message, null, null)
        return CommandResult(true, "sms sent to $number", null)
    }

    private suspend fun sendWhatsApp(number: String, message: String): CommandResult {
        val clean = number.replace(Regex("[^\\d]"), "")
        val url = "https://api.whatsapp.com/send?phone=$clean&text=${URLEncoder.encode(message, "UTF-8")}"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            .setPackage("com.whatsapp")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
        } catch (e: Exception) {
            return CommandResult(false, null, "WhatsApp not installed or not reachable: ${e.message}")
        }
        delay(1_500)
        val service = FridayAccessibilityService.instance
            ?: return CommandResult(
                false,
                "WhatsApp chat opened with the message typed in. Accessibility is not enabled, " +
                    "so the send tap is still yours — the message is NOT sent yet.",
                "prefilled_only_manual_send_required"
            )
        return if (service.clickWhatsAppSend()) {
            CommandResult(true, "whatsapp message sent to $clean", null)
        } else {
            CommandResult(false, "chat opened but the Send button was not found on screen", "send_button_not_found")
        }
    }

    private fun readNotifications(limit: Int): CommandResult {
        val listener = FridayNotificationListener.instance
            ?: return CommandResult(false, null, "notification access is not granted to FRIDAY Companion")
        val arr = JSONArray()
        listener.snapshot(limit.coerceIn(1, 100)).forEach { item ->
            arr.put(JSONObject().put("app", item["app"]).put("title", item["title"]).put("text", item["text"]))
        }
        return CommandResult(true, arr.toString(), null)
    }

    private fun setAlarm(hour: Int, minute: Int, label: String): CommandResult {
        val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
            putExtra(AlarmClock.EXTRA_HOUR, hour)
            putExtra(AlarmClock.EXTRA_MINUTES, minute)
            putExtra(AlarmClock.EXTRA_MESSAGE, label.ifEmpty { "FRIDAY alarm" })
            putExtra(AlarmClock.EXTRA_SKIP_UI, true)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return CommandResult(true, "alarm set for %02d:%02d".format(hour, minute), null)
    }

    private fun mediaControl(action: String): CommandResult {
        val keyCode = when (action.lowercase()) {
            "play" -> KeyEvent.KEYCODE_MEDIA_PLAY
            "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
            "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            "stop" -> KeyEvent.KEYCODE_MEDIA_STOP
            else -> return CommandResult(false, null, "unknown media action '$action'")
        }
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
        return CommandResult(true, "media $action", null)
    }

    private fun setVolume(percent: Int, streamName: String): CommandResult {
        val stream = when (streamName.lowercase()) {
            "ring" -> AudioManager.STREAM_RING
            "call" -> AudioManager.STREAM_VOICE_CALL
            else -> AudioManager.STREAM_MUSIC
        }
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val max = audio.getStreamMaxVolume(stream)
        val index = (percent.coerceIn(0, 100) / 100.0 * max).toInt()
        audio.setStreamVolume(stream, index, 0)
        return CommandResult(true, "volume set to $index/$max", null)
    }

    private suspend fun findPhone(seconds: Int): CommandResult {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val previous = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC), 0)
        val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
        val ringtone = RingtoneManager.getRingtone(context, uri)
        ringtone.play()
        delay(seconds.coerceIn(5, 120) * 1000L)
        ringtone.stop()
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, previous, 0)
        return CommandResult(true, "rang at full volume for ${seconds.coerceIn(5, 120)}s", null)
    }

    private fun withAccessibility(command: String, block: (FridayAccessibilityService) -> Boolean): CommandResult {
        val service = FridayAccessibilityService.instance
            ?: return CommandResult(false, null, "'$command' needs FRIDAY's accessibility service — enable it in Settings > Accessibility > FRIDAY phone control")
        return if (block(service)) {
            CommandResult(true, "$command done", null)
        } else {
            CommandResult(false, null, "accessibility service refused '$command'")
        }
    }

    private fun pressKey(key: String): CommandResult {
        val service = FridayAccessibilityService.instance
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        return when (key.lowercase()) {
            "home" -> globalAction(service, AccessibilityService.GLOBAL_ACTION_HOME, "home")
            "back" -> globalAction(service, AccessibilityService.GLOBAL_ACTION_BACK, "back")
            "app_switch" -> globalAction(service, AccessibilityService.GLOBAL_ACTION_RECENTS, "app_switch")
            "volume_up" -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, 0)
                CommandResult(true, "volume up", null)
            }
            "volume_down" -> {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, 0)
                CommandResult(true, "volume down", null)
            }
            "media_play_pause" -> mediaControl("pause")
            "media_next" -> mediaControl("next")
            "media_previous" -> mediaControl("previous")
            else -> CommandResult(false, null, "companion app cannot press '$key'")
        }
    }

    private fun globalAction(service: FridayAccessibilityService?, action: Int, name: String): CommandResult {
        if (service == null) {
            return CommandResult(false, null, "'$name' needs FRIDAY's accessibility service enabled")
        }
        return if (service.pressGlobal(action)) {
            CommandResult(true, "pressed $name", null)
        } else {
            CommandResult(false, null, "accessibility service refused '$name'")
        }
    }

    private suspend fun screenshot(): CommandResult {
        val service = FridayAccessibilityService.instance
            ?: return CommandResult(false, null, "screenshot needs FRIDAY's accessibility service enabled (Android 11+)")
        val base64 = service.screenshotBase64()
            ?: return CommandResult(false, null, "screenshot failed (needs Android 11+ and the accessibility service)")
        return CommandResult(true, base64, null)
    }

    companion object {
        val BASE_CAPABILITIES = listOf(
            "device_status", "open_app", "close_app", "open_url", "make_call",
            "send_sms", "send_whatsapp", "set_alarm", "media_control",
            "set_volume", "find_phone"
        )
        val ACCESSIBILITY_CAPABILITIES = listOf(
            "tap", "swipe", "type_text", "press_key", "screenshot"
        )
        val APP_PACKAGES = mapOf(
            "youtube" to "com.google.android.youtube",
            "chrome" to "com.android.chrome",
            "maps" to "com.google.android.apps.maps",
            "camera" to "com.android.camera",
            "settings" to "com.android.settings",
            "messages" to "com.google.android.apps.messaging",
            "phone" to "com.google.android.dialer",
            "contacts" to "com.google.android.contacts",
            "calculator" to "com.google.android.calculator",
            "clock" to "com.google.android.deskclock",
            "calendar" to "com.google.android.calendar",
            "photos" to "com.google.android.apps.photos",
            "gmail" to "com.google.android.gm",
            "playstore" to "com.android.vending",
            "whatsapp" to "com.whatsapp",
            "spotify" to "com.spotify.music",
            "instagram" to "com.instagram.android",
            "telegram" to "org.telegram.messenger",
            "netflix" to "com.netflix.ninja"
        )
    }
}
