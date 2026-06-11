package com.example.carpayin.vehicle

import ai.pleos.playground.tts.TextToSpeech
import ai.pleos.playground.tts.constant.Mode
import ai.pleos.playground.tts.listener.OnServerConnectionListener
import ai.pleos.playground.tts.listener.TtsEventListener
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
            tts = TextToSpeech(context.applicationContext, Mode.HYBRID)
            tts?.initialize()
            tts?.addEventListener(eventListener)
            tts?.registerApp(CLIENT_ID, CLIENT_SECRET, object : OnServerConnectionListener {
                override fun onConnected() {
                    isReady = true
                    Log.d(TAG, "TTS 서버 연결 완료")
                }
                override fun onFailed(msg: String) {
                    Log.w(TAG, "TTS 서버 연결 실패: $msg — ON_DEVICE 모드로 재시도")
                    retryOnDevice(context)
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "TTS 초기화 실패: ${e.message}")
        }
    }

    private fun retryOnDevice(context: Context) {
        try {
            tts?.removeEventListener(eventListener)
            tts?.release()
            tts = TextToSpeech(context.applicationContext, Mode.ON_DEVICE)
            tts?.initialize()
            tts?.addEventListener(eventListener)
            tts?.registerApp(CLIENT_ID, CLIENT_SECRET, object : OnServerConnectionListener {
                override fun onConnected() { isReady = true; Log.d(TAG, "TTS ON_DEVICE 연결 완료") }
                override fun onFailed(msg: String) { Log.w(TAG, "TTS ON_DEVICE 실패: $msg") }
            })
        } catch (e: Exception) {
            Log.w(TAG, "TTS ON_DEVICE 초기화 실패: ${e.message}")
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

    private val eventListener = object : TtsEventListener {
        override fun onSpeakStart() { Log.d(TAG, "onSpeakStart") }
        override fun onSpeakDone()  { Log.d(TAG, "onSpeakDone") }
        override fun onSpeakError(msg: String) { Log.w(TAG, "onSpeakError: $msg") }
    }
}
