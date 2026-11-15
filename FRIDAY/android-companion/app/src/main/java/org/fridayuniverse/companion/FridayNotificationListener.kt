package org.fridayuniverse.companion

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

/**
 * Holds the phone's current notification snapshot for `read_notifications`.
 * Android delivers notifications to this service only after the owner grants
 * Notification Access to FRIDAY Companion in Settings.
 */
class FridayNotificationListener : NotificationListenerService() {

    override fun onListenerConnected() {
        instance = this
    }

    override fun onListenerDisconnected() {
        if (instance === this) instance = null
    }

    fun snapshot(limit: Int): List<Map<String, String?>> {
        val active: Array<StatusBarNotification> = try {
            activeNotifications ?: emptyArray()
        } catch (e: Exception) {
            emptyArray()
        }
        return active.take(limit).map { sbn ->
            val extras = sbn.notification.extras
            mapOf(
                "app" to sbn.packageName,
                "title" to extras.getCharSequence(Notification.EXTRA_TITLE)?.toString(),
                "text" to extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
            )
        }
    }

    companion object {
        @Volatile
        var instance: FridayNotificationListener? = null
            private set
    }
}
