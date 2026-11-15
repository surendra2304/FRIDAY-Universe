package org.fridayuniverse.companion

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * Pairing + grants screen. The owner's whole setup is:
 *   1. enter the 6-digit code FRIDAY shows him, tap Pair;
 *   2. tap each grant button once (permissions, accessibility,
 *      notification access, battery exemption);
 *   3. tap Start. The bridge then stays connected on its own.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var status: TextView
    private val http = OkHttpClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
        }
        val baseUrl = EditText(this).apply {
            setText(Prefs.baseUrl(this@MainActivity))
            hint = "FRIDAY address"
        }
        val deviceName = EditText(this).apply { hint = "Phone name (e.g. My Pixel)" }
        val code = EditText(this).apply {
            hint = "6-digit pairing code from FRIDAY"
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
        }
        status = TextView(this)

        root.addView(baseUrl)
        root.addView(deviceName)
        root.addView(code)
        root.addView(Button(this).apply {
            text = "Pair this phone"
            setOnClickListener { pair(baseUrl.text.toString(), code.text.toString(), deviceName.text.toString()) }
        })
        root.addView(Button(this).apply {
            text = "Start FRIDAY connection"
            setOnClickListener {
                PhoneBridgeService.start(this@MainActivity)
                refreshStatus()
            }
        })
        root.addView(Button(this).apply {
            text = "Stop FRIDAY connection"
            setOnClickListener {
                PhoneBridgeService.stop(this@MainActivity)
                refreshStatus()
            }
        })
        root.addView(Button(this).apply {
            text = "Grant call + SMS permissions"
            setOnClickListener {
                ActivityCompat.requestPermissions(
                    this@MainActivity,
                    arrayOf(
                        Manifest.permission.CALL_PHONE,
                        Manifest.permission.SEND_SMS,
                        Manifest.permission.POST_NOTIFICATIONS
                    ),
                    1
                )
            }
        })
        root.addView(Button(this).apply {
            text = "Enable accessibility (tap / type / screenshot)"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        })
        root.addView(Button(this).apply {
            text = "Grant notification access (read notifications)"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        })
        root.addView(Button(this).apply {
            text = "Exempt from battery optimisation (stay connected)"
            setOnClickListener {
                val intent = Intent(
                    Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
        })
        root.addView(status)
        setContentView(root)
        refreshStatus()
    }

    override fun onResume() {
        super.onResume()
        if (::status.isInitialized) refreshStatus()
    }

    private fun refreshStatus() {
        val paired = Prefs.isPaired(this)
        status.text = buildString {
            append(if (paired) "Paired as ${Prefs.deviceId(this@MainActivity)}\n" else "Not paired yet.\n")
            append("Accessibility: ${if (FridayAccessibilityService.instance != null) "on" else "off"}\n")
            append("Notification access: ${if (FridayNotificationListener.instance != null) "on" else "off"}")
        }
    }

    private fun pair(baseUrlRaw: String, codeRaw: String, name: String) {
        val baseUrl = baseUrlRaw.trim().trimEnd('/')
        val code = codeRaw.trim()
        if (code.length != 6) {
            Toast.makeText(this, "The pairing code is 6 digits", Toast.LENGTH_SHORT).show()
            return
        }
        CoroutineScope(Dispatchers.IO).launch {
            val outcome = try {
                val body = JSONObject()
                    .put("pairing_code", code)
                    .put("device_name", name.ifEmpty { "Android phone" })
                    .put("executor", "companion-app")
                    .toString()
                    .toRequestBody("application/json".toMediaType())
                val request = Request.Builder().url("$baseUrl/api/phone/pair").post(body).build()
                http.newCall(request).execute().use { response ->
                    val text = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        "Pairing failed (${response.code}): $text"
                    } else {
                        val json = JSONObject(text)
                        Prefs.savePairing(
                            this@MainActivity, baseUrl,
                            json.getString("device_id"), json.getString("device_token")
                        )
                        PhoneBridgeService.start(this@MainActivity)
                        "Paired and connecting…"
                    }
                }
            } catch (e: Exception) {
                "Pairing failed: ${e.message}"
            }
            withContext(Dispatchers.Main) {
                Toast.makeText(this@MainActivity, outcome, Toast.LENGTH_LONG).show()
                refreshStatus()
            }
        }
    }
}
