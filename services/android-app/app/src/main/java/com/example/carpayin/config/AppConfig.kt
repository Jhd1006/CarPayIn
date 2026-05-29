package com.example.carpayin.config

import com.example.carpayin.BuildConfig

object AppConfig {
    val backendBaseUrl: String = BuildConfig.CARPAYIN_BACKEND_BASE_URL.trimEnd('/')
    val qrBaseUrl: String = BuildConfig.CARPAYIN_QR_BASE_URL.trimEnd('/')
    val mqttBrokerUrl: String = BuildConfig.CARPAYIN_MQTT_BROKER_URL
    private val rewriteLocalhostForEmulator: Boolean = BuildConfig.CARPAYIN_EMULATOR_LOCALHOST_REWRITE

    fun normalizeLocalhostForDevice(url: String): String {
        if (!rewriteLocalhostForEmulator) return url
        return url
            .replace("://localhost:", "://10.0.2.2:")
            .replace("://127.0.0.1:", "://10.0.2.2:")
    }
}
