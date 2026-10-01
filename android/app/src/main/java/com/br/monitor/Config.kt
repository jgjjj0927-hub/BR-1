package com.br.monitor

object Config {
    const val SERVER_URL = "https://panel.br-v2.ru"
    const val WS_URL = "wss://panel.br-v2.ru/ws"
    const val API_URL = "https://panel.br-v2.ru/api"
    const val GEO_INTERVAL_MS = 5_000L      // каждые 5 сек
    const val RECONNECT_DELAY_MS = 10_000L  // переподключение WS
    const val OFFLINE_FLUSH_INTERVAL_MS = 30_000L
}
