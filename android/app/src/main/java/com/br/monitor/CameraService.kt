package com.br.monitor

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import kotlinx.coroutines.*
import java.util.concurrent.Executors

class CameraService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val executor = Executors.newSingleThreadExecutor()

    private val lifecycleOwner = object : LifecycleOwner {
        val registry = LifecycleRegistry(this)
        override val lifecycle: Lifecycle get() = registry
    }

    companion object {
        const val EXTRA_FACING = "facing"
    }

    override fun onCreate() {
        super.onCreate()
        lifecycleOwner.registry.currentState = Lifecycle.State.CREATED
        lifecycleOwner.registry.currentState = Lifecycle.State.STARTED
        lifecycleOwner.registry.currentState = Lifecycle.State.RESUMED
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val facing = intent?.getStringExtra(EXTRA_FACING) ?: "back"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NotifIds.CAMERA, buildNotif(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
        } else {
            startForeground(NotifIds.CAMERA, buildNotif())
        }
        capturePhoto(facing)
        return START_NOT_STICKY
    }

    private fun capturePhoto(facing: String) {
        val lensFacing = if (facing == "front") CameraSelector.LENS_FACING_FRONT
                         else CameraSelector.LENS_FACING_BACK

        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()

            val selector = CameraSelector.Builder()
                .requireLensFacing(lensFacing)
                .build()

            val capture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .setFlashMode(ImageCapture.FLASH_MODE_OFF)
                .build()

            try {
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, selector, capture)
            } catch (e: Exception) {
                Log.e("CameraService", "Bind failed: ${e.message}")
                finish()
                return@addListener
            }

            capture.takePicture(executor, object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val plane = image.planes[0]
                    val buf = plane.buffer
                    val bytes = ByteArray(buf.remaining())
                    buf.get(bytes)
                    image.close()
                    provider.unbindAll()

                    scope.launch {
                        ApiClient.postBytes("/photo?facing=$facing", bytes, "image/jpeg")
                        finish()
                    }
                }

                override fun onError(exc: ImageCaptureException) {
                    Log.e("CameraService", "Capture error: ${exc.message}")
                    provider.unbindAll()
                    finish()
                }
            })
        }, ContextCompat.getMainExecutor(this))
    }

    private fun finish() {
        lifecycleOwner.registry.currentState = Lifecycle.State.DESTROYED
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        executor.shutdown()
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotif(): Notification {
        val ch = "cam"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(ch, "Camera", NotificationManager.IMPORTANCE_LOW)
            )
        }
        return NotificationCompat.Builder(this, ch)
            .setContentTitle("Camera")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
