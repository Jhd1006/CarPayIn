package com.example.carpayin.vehicle

import ai.pleos.playground.tts.TextToSpeech
import ai.pleos.playground.tts.constant.Mode
import ai.pleos.playground.tts.listener.EventListener
import ai.pleos.playground.tts.listener.OnServerConnectionListener
import android.content.Context
import android.util.Log

object TtsHelper {

    private const val TAG = "TtsHelper"
    private const val CLIENT_ID     = "2iRta3KrTgKs4-S5kCW-gw"
    private const val CLIENT_SECRET = "8fe2c127-d231-4342-b681-5ef70f346265"

    private var tts: TextToSpeech? = null
    private var isReady = false

    fun init(context: Context) {
        if (tts != null) return
        try {
            tts = TextToSpeech(context.applicationContext, Mode.ON_DEVICE)
            tts?.initialize()
            tts?.addEventListener(eventListener)
            tts?.registerApp(CLIENT_ID, CLIENT_SECRET, object : OnServerConnectionListener {
                override fun onConnected() { isReady = true; Log.d(TAG, "TTS 준비 완료") }
                override fun onFailed(msg: String) { Log.w(TAG, "TTS 초기화 실패: $msg") }
            })
        } catch (e: Exception) {
            Log.w(TAG, "TTS 초기화 실패: ${e.message}")
        }
    }

    fun speak(text: String) {
        if (!isReady) { Log.d(TAG, "TTS 미준비 — 무시: $text"); return }
        try {
            tts?.speak(text)
            Log.d(TAG, "TTS speak: $text")
        } catch (e: Exception) {
            Log.w(TAG, "TTS speak 실패: ${e.message}")
        }
    }

    fun stop() {
        try { tts?.stop() } catch (_: Exception) {}
    }

    fun release() {
        try {
            tts?.removeEventListener(eventListener)
            tts?.release()
        } catch (_: Exception) {}
        tts = null
        isReady = false
    }

    private val eventListener = object : EventListener {
        override fun onReady()  { Log.d(TAG, "onReady") }
        override fun onStart()  { Log.d(TAG, "onStart") }
        override fun onDone()   { Log.d(TAG, "onDone") }
        override fun onStop()   { Log.d(TAG, "onStop") }
        override fun onError(errMsg: String) { Log.w(TAG, "onError: $errMsg") }
        override fun onUpdatedRms(rms: Double) {}
    }
}
