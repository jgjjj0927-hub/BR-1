package com.br.monitor

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle

// Transparent trampoline — requests MediaProjection permission then hands result to ScreenService
class ScreenCaptureActivity : Activity() {

    companion object {
        const val REQ = 1001
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val mgr = getSystemService(MediaProjectionManager::class.java)
        startActivityForResult(mgr.createScreenCaptureIntent(), REQ)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ && resultCode == RESULT_OK && data != null) {
            val svc = Intent(this, ScreenService::class.java).apply {
                putExtra(ScreenService.EXTRA_CODE, resultCode)
                putExtra(ScreenService.EXTRA_DATA, data)
            }
            startForegroundService(svc)
        }
        finish()
    }
}
