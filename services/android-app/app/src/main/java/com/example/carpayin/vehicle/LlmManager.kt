package com.example.carpayin.vehicle

import ai.pleos.playground.llm.LLM
import ai.pleos.playground.llm.data.LLMContent
import ai.pleos.playground.llm.data.TextPart
import ai.pleos.playground.llm.listener.OnServerConnectionListener
import ai.pleos.playground.llm.listener.ResultListener
import android.content.Context
import android.util.Log
import com.example.carpayin.BuildConfig

object LlmManager {

    private const val TAG = "LlmManager"

    private var llm: LLM? = null
    var isReady = false
        private set

    fun init(context: Context) {
        if (llm != null) return
        try {
            llm = LLM(context.applicationContext)
            llm?.initialize()
            llm?.registerApp(BuildConfig.PLEOS_CLIENT_ID, BuildConfig.PLEOS_CLIENT_SECRET, object : OnServerConnectionListener {
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

    fun startChat(systemPrompt: String, onReady: () -> Unit = {}) {
        try {
            val history = mutableListOf(
                LLMContent(role = "user",      parts = mutableListOf(TextPart(systemPrompt))),
                LLMContent(role = "assistant", parts = mutableListOf(TextPart("네, 도와드리겠습니다.")))
            )
            llm?.startChat(history, { onReady() }, { reason -> Log.w(TAG, "startChat 실패: $reason") })
        } catch (e: Exception) {
            Log.w(TAG, "startChat 실패: ${e.message}")
        }
    }

    fun send(text: String, onComplete: (String) -> Unit, onError: () -> Unit = {}) {
        if (!isReady) { Log.d(TAG, "LLM 미준비"); onError(); return }
        val buffer = StringBuilder()
        try {
            val content = LLMContent(role = "user", parts = mutableListOf(TextPart(text)))
            llm?.sendMessage(content, object : ResultListener {
                override fun onResponse(response: String, completed: Boolean) {
                    buffer.append(response)
                    if (completed) {
                        val full = buffer.toString().trim()
                        Log.d(TAG, "LLM 응답: $full")
                        onComplete(full)
                    }
                }
                override fun onError(reason: String) {
                    Log.w(TAG, "LLM 오류: $reason")
                    onError()
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "send 실패: ${e.message}")
            onError()
        }
    }

    fun release() {
        try { llm?.release() } catch (_: Exception) {}
        llm = null
        isReady = false
    }
}
