package org.fridayuniverse.companion

import android.content.Context
import android.content.SharedPreferences

/**
 * Pairing credentials + server base URL.
 *
 * NOTE (scaffold hardening): the device token is a bearer credential. Before
 * any non-owner distribution, move it to EncryptedSharedPreferences
 * (androidx.security:security-crypto); for the owner's own sideloaded build
 * the app-private SharedPreferences file is already sandboxed per-app.
 */
object Prefs {
    private const val FILE = "friday_companion"
    private const val KEY_BASE_URL = "base_url"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_DEVICE_TOKEN = "device_token"

    const val DEFAULT_BASE_URL = "https://friday-universe.duckdns.org/friday"

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun baseUrl(context: Context): String =
        prefs(context).getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL

    fun deviceId(context: Context): String? = prefs(context).getString(KEY_DEVICE_ID, null)

    fun deviceToken(context: Context): String? = prefs(context).getString(KEY_DEVICE_TOKEN, null)

    fun isPaired(context: Context): Boolean = deviceId(context) != null && deviceToken(context) != null

    fun savePairing(context: Context, baseUrl: String, deviceId: String, deviceToken: String) {
        prefs(context).edit()
            .putString(KEY_BASE_URL, baseUrl.trimEnd('/'))
            .putString(KEY_DEVICE_ID, deviceId)
            .putString(KEY_DEVICE_TOKEN, deviceToken)
            .apply()
    }

    fun clearPairing(context: Context) {
        prefs(context).edit().remove(KEY_DEVICE_ID).remove(KEY_DEVICE_TOKEN).apply()
    }
}
