package com.br.monitor

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

object ApiClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val JSON = "application/json".toMediaType()

    suspend fun post(endpoint: String, body: JSONObject): Boolean = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("${Config.API_URL}$endpoint")
                .post(body.toString().toRequestBody(JSON))
                .build()
            val resp = client.newCall(req).execute()
            resp.close()
            resp.isSuccessful
        } catch (e: IOException) {
            Log.w("ApiClient", "POST $endpoint failed: ${e.message}")
            false
        }
    }

    suspend fun postBytes(endpoint: String, bytes: ByteArray, mime: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val body = bytes.toRequestBody(mime.toMediaType())
                val req = Request.Builder()
                    .url("${Config.API_URL}$endpoint")
                    .post(body)
                    .build()
                val resp = client.newCall(req).execute()
                resp.close()
                resp.isSuccessful
            } catch (e: IOException) {
                Log.w("ApiClient", "POST bytes $endpoint failed: ${e.message}")
                false
            }
        }

    fun isOnline(): Boolean {
        return try {
            val req = Request.Builder().url("${Config.API_URL}/ping").get().build()
            val resp = client.newCall(req).execute()
            resp.close()
            resp.isSuccessful
        } catch (_: Exception) {
            false
        }
    }
}
