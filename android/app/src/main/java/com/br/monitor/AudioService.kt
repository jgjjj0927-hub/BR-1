package com.br.monitor

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import okhttp3.*
import okio.ByteString
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit

class AudioService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var recorder: AudioRecord? = null
    private var streaming = false
    private var ws: WebSocket? = null

    private val wsClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // бесконечный таймаут для стрима
        .build()

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NotifIds.AUDIO, buildNotif(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NotifIds.AUDIO, buildNotif())
        }
        connectWs()
    }

    private fun connectWs() {
        val req = Request.Builder().url("${Config.WS_URL}/audio").build()
        ws = wsClient.newWebSocket(req, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                when (text.trim()) {
                    "start" -> startStreaming()
                    "stop"  -> stopStreaming()
                }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w("AudioService", "WS fail: ${t.message}")
                scope.launch {
                    delay(Config.RECONNECT_DELAY_MS)
                    connectWs()
                }
            }
        })
    }

    private fun startStreaming() {
        if (streaming) return
        streaming = true

        val sampleRate = 16_000
        val bufSize = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        ) * 4

        recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufSize
        )

        recorder?.startRecording()

        scope.launch {
            val buf = ByteArray(bufSize)
            while (streaming && isActive) {
                val read = recorder?.read(buf, 0, bufSize) ?: break
                if (read > 0) {
                    ws?.send(buf.copyOf(read).toByteString())
                }
            }
        }
    }

    private fun stopStreaming() {
        streaming = false
        recorder?.stop()
        recorder?.release()
        recorder = null
        // Уведомление пропадает — сервис останавливается
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        stopStreaming()
        ws?.close(1000, null)
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotif(): Notification {
        val ch = "audio"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(ch, "Audio", NotificationManager.IMPORTANCE_LOW)
            )
        }
        return NotificationCompat.Builder(this, ch)
            .setContentTitle("Audio")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
