package com.example.carpayin.vehicle

import ai.pleos.playground.stt.SpeechToText
import ai.pleos.playground.stt.constant.Mode
import ai.pleos.playground.stt.listener.OnServerConnectionListener
import ai.pleos.playground.stt.listener.ResultListener
import android.content.Context
import android.util.Log

object SttManager {

    private const val TAG = "SttManager"
    private const val CLIENT_ID     = "2iRta3KrTgKs4-S5kCW-gw"
    private const val CLIENT_SECRET = "8fe2c127-d231-4342-b681-5ef70f346265"

    private var stt: SpeechToText? = null
    private var isReady = false
    var isListening = false
        private set

    var onResult: ((text: String) -> Unit)? = null
    var onListeningChanged: ((listening: Boolean) -> Unit)? = null

    fun init(context: Context) {
        if (stt != null) return
        try {
            stt = SpeechToText(context.applicationContext, Mode.HYBRID)
            stt?.initialize()
            stt?.addListener(resultListener)
            stt?.registerApp(CLIENT_ID, CLIENT_SECRET, object : OnServerConnectionListener {
                override fun onConnected() {
                    isReady = true
                    Log.d(TAG, "STT 준비 완료")
                }
                override fun onFailed(msg: String) {
                    Log.w(TAG, "STT 초기화 실패: $msg")
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "STT 초기화 실패: ${e.message}")
        }
    }

    fun toggleListening() {
        if (!isReady) {
            Log.d(TAG, "STT 미준비")
            return
        }
        if (isListening) stopListening() else startListening()
    }

    private fun startListening() {
        try {
            stt?.request()
            isListening = true
            onListeningChanged?.invoke(true)
            Log.d(TAG, "STT 시작")
        } catch (e: Exception) {
            Log.w(TAG, "STT request 실패: ${e.message}")
        }
    }

    private fun stopListening() {
        try {
            stt?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "STT stop 실패: ${e.message}")
        }
        isListening = false
        onListeningChanged?.invoke(false)
    }

    fun release() {
        try {
            stt?.removeListener(resultListener)
            stt?.release()
        } catch (_: Exception) {}
        stt = null
        isReady = false
        isListening = false
    }

    private val resultListener = object : ResultListener {
        override fun onReady() { Log.d(TAG, "onReady") }

        override fun onStartedRecognition() {
            Log.d(TAG, "onStartedRecognition")
        }

        override fun onEndedRecognition() {
            Log.d(TAG, "onEndedRecognition")
            isListening = false
            onListeningChanged?.invoke(false)
        }

        override fun onUpdated(results: List<*>, isFinal: Boolean) {
            if (!isFinal || results.isEmpty()) return
            val text = results.first()?.toString()?.trim() ?: return
            if (text.isBlank()) return
            Log.d(TAG, "STT 결과: \"$text\"")
            onResult?.invoke(text)
        }

        override fun onUpdatedEpdData(data: Any?) {}

        override fun onError(errMsg: String) {
            Log.w(TAG, "STT 오류: $errMsg")
            isListening = false
            onListeningChanged?.invoke(false)
        }
    }
}
