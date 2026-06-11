package com.example.carpayin.vehicle

import ai.pleos.playground.llm.LLM
import ai.pleos.playground.llm.listener.OnServerConnectionListener
import ai.pleos.playground.llm.listener.ResultListener
import android.content.Context
import android.util.Log

object LlmManager {

    private const val TAG = "LlmManager"
    private const val CLIENT_ID     = "2iRta3KrTgKs4-S5kCW-gw"
    private const val CLIENT_SECRET = "8fe2c127-d231-4342-b681-5ef70f346265"

    private var llm: LLM? = null
    var isReady = false
        private set

    fun init(context: Context) {
        if (llm != null) return
        try {
            llm = LLM(context.applicationContext)
            llm?.initialize()
            llm?.registerApp(CLIENT_ID, CLIENT_SECRET, object : OnServerConnectionListener {
                override fun onConnected() {
                    isReady = true
                    Log.d(TAG, "LLM 준비 완료")
                }
                override fun onFailed(msg: String) {
                    Log.w(TAG, "LLM 초기화 실패: $msg")
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "LLM 초기화 실패: ${e.message}")
        }
    }

    fun generate(prompt: String, onComplete: (String) -> Unit, onError: () -> Unit = {}) {
        if (!isReady) { Log.d(TAG, "LLM 미준비"); onError(); return }
        try {
            llm?.generateContent(prompt, object : ResultListener {
                private val buffer = StringBuilder()

                override fun onPartialResult(text: String) {
                    buffer.append(text)
                }

                override fun onResult(text: String) {
                    val full = text.ifBlank { buffer.toString() }.trim()
                    Log.d(TAG, "LLM 응답: $full")
                    onComplete(full)
                }

                override fun onError(errMsg: String) {
                    Log.w(TAG, "LLM 오류: $errMsg")
                    onError()
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "generate 실패: ${e.message}")
            onError()
        }
    }

    fun release() {
        try { llm?.release() } catch (_: Exception) {}
        llm = null
        isReady = false
    }
}
