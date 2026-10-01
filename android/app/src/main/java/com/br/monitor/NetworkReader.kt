package com.br.monitor

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

object NetworkReader {

    suspend fun readAndSend(context: Context, buffer: OfflineBuffer) = withContext(Dispatchers.IO) {
        try {
            val cm = context.getSystemService(ConnectivityManager::class.java)
            val net = cm.activeNetwork
            val caps = cm.getNetworkCapabilities(net)

            val type = when {
                caps == null -> "none"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                else -> "other"
            }

            val ssid = if (type == "wifi") getWifiSsid(context) else ""

            val payload = JSONObject().apply {
                put("type", type)
                put("ssid", ssid)
                put("ts",   System.currentTimeMillis())
            }

            val ok = ApiClient.post("/network", payload)
            if (!ok) buffer.push("network", payload.toString())

        } catch (e: Exception) {
            Log.w("NetworkReader", "Failed: ${e.message}")
        }
    }

    @Suppress("DEPRECATION")
    private fun getWifiSsid(context: Context): String {
        return try {
            val wm = context.applicationContext.getSystemService(WifiManager::class.java)
            val info = wm.connectionInfo
            info.ssid?.removeSurrounding("\"") ?: ""
        } catch (_: Exception) { "" }
    }
}
