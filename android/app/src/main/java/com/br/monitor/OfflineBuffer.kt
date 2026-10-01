package com.br.monitor

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.content.ContentValues
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class OfflineBuffer(context: Context) : SQLiteOpenHelper(context, "buffer.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                ts INTEGER NOT NULL
            )
        """)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS events")
        onCreate(db)
    }

    fun push(type: String, payload: String) {
        val cv = ContentValues().apply {
            put("type", type)
            put("payload", payload)
            put("ts", System.currentTimeMillis())
        }
        writableDatabase.insert("events", null, cv)
    }

    fun popAll(): List<Triple<Int, String, String>> {
        val result = mutableListOf<Triple<Int, String, String>>()
        val cur = readableDatabase.rawQuery(
            "SELECT id, type, payload FROM events ORDER BY id LIMIT 100", null
        )
        cur.use {
            while (it.moveToNext()) {
                result.add(Triple(it.getInt(0), it.getString(1), it.getString(2)))
            }
        }
        return result
    }

    fun delete(ids: List<Int>) {
        if (ids.isEmpty()) return
        writableDatabase.execSQL("DELETE FROM events WHERE id IN (${ids.joinToString(",")})")
    }

    suspend fun flush(send: suspend (type: String, payload: String) -> Boolean) =
        withContext(Dispatchers.IO) {
            val rows = popAll()
            if (rows.isEmpty()) return@withContext
            val flushed = mutableListOf<Int>()
            for ((id, type, payload) in rows) {
                if (send(type, payload)) flushed.add(id)
            }
            if (flushed.isNotEmpty()) delete(flushed)
        }
}
