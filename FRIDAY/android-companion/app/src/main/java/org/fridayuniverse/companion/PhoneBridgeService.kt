package org.fridayuniverse.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import java.time.Instant
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject

/**
 * The reverse tunnel. A foreground service holds one outbound WSS
 * connection to FRIDAY and reconnects with backoff forever — the phone
 * finds FRIDAY, never the other way round, so carrier NAT, network changes
 * and Doze (with the battery exemption) cannot strand it.
 *
 * Frames mirror friday/remote/phone_bridge.py: hello (with the live
 * capability map), command, result, ping/pong.
 */
class PhoneBridgeService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var sessionJob: Job? = null
    private var socket: WebSocket? = null
    @Volatile private var stopped = true

    private val client = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundNotification()
        if (stopped) {
            stopped = false
            sessionJob = scope.launch { runForever() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopped = true
        sessionJob?.cancel()
        socket?.close(1000, "service stopped")
        scope.cancel()
        super.onDestroy()
    }

    private fun startForegroundNotification() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW)
        )
        val notification: Notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("FRIDAY Companion")
            .setContentText("Connected to FRIDAY — your phone takes its commands only from your FRIDAY.")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private suspend fun runForever() {
        var backoffMs = 5_000L
        while (!stopped) {
            val connected = runSession()
            if (stopped) break
            if (connected) backoffMs = 5_000L
            delay(backoffMs)
            backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
        }
    }

    /** One tunnel lifetime. Returns true if a session was established. */
    private suspend fun runSession(): Boolean {
        val deviceId = Prefs.deviceId(this) ?: return false
        val token = Prefs.deviceToken(this) ?: return false
        val base = Prefs.baseUrl(this)
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        val request = Request.Builder()
            .url("$base/api/phone/connect/$deviceId")
            .header("Authorization", "Bearer $token")
            .build()

        val dispatcher = CommandDispatcher(applicationContext)
        val connected = kotlinx.coroutines.CompletableDeferred<Boolean>()
        val closed = kotlinx.coroutines.CompletableDeferred<Unit>()

        val listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                socket = webSocket
                val hello = JSONObject()
                    .put("type", "hello")
                    .put("executor", "companion-app")
                    .put("capabilities", org.json.JSONArray(dispatcher.advertisedCapabilities()))
                webSocket.send(hello.toString())
                connected.complete(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val frame = try {
                    JSONObject(text)
                } catch (e: Exception) {
                    return
                }
                when (frame.optString("type")) {
                    "command" -> scope.launch {
                        val started = Instant.now().toString()
                        val args = frame.optJSONObject("args") ?: JSONObject()
                        val result = dispatcher.execute(frame.optString("command"), args)
                        val payload = JSONObject()
                            .put("type", "result")
                            .put("request_id", frame.optString("request_id"))
                            .put("started_at", started)
                            .put("finished_at", Instant.now().toString())
                            .put("ok", result.ok)
                            .put("output", result.output ?: JSONObject.NULL)
                            .put("error", result.error ?: JSONObject.NULL)
                        webSocket.send(payload.toString())
                    }
                    "ping" -> webSocket.send(JSONObject().put("type", "pong").toString())
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (!connected.isCompleted) connected.complete(false)
                closed.complete(Unit)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (!connected.isCompleted) connected.complete(false)
                closed.complete(Unit)
            }
        }

        client.newWebSocket(request, listener)
        val wasConnected = connected.await()
        closed.await()
        socket = null
        return wasConnected
    }

    companion object {
        private const val CHANNEL_ID = "friday_bridge"
        private const val NOTIFICATION_ID = 1001

        fun start(context: android.content.Context) {
            val intent = Intent(context, PhoneBridgeService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: android.content.Context) {
            context.stopService(Intent(context, PhoneBridgeService::class.java))
        }
    }
}
