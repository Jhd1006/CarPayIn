package com.example.carpayin.vehicle

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

object TtsHelper {

    private const val TAG = "TtsHelper"

    private var tts: TextToSpeech? = null
    private var isReady = false

    fun init(context: Context) {
        if (tts != null) return
        tts = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val result = tts?.setLanguage(Locale.KOREAN)
                isReady = result != TextToSpeech.LANG_MISSING_DATA
                        && result != TextToSpeech.LANG_NOT_SUPPORTED
                if (isReady) Log.d(TAG, "TTS 준비 완료")
                else Log.w(TAG, "한국어 TTS 미지원")
            } else {
                Log.w(TAG, "TTS 초기화 실패: status=$status")
            }
        }
    }

    fun speak(text: String) {
        if (!isReady) { Log.d(TAG, "TTS 미준비 — 무시: $text"); return }
        tts?.speak(text, TextToSpeech.QUEUE_ADD, null, null)
    }

    fun stop() {
        tts?.stop()
    }

    fun release() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }
}
