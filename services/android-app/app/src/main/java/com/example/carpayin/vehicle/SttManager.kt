package com.example.carpayin.vehicle

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

object SttManager {

    private const val TAG = "SttManager"

    private var recognizer: SpeechRecognizer? = null
    var isReady = false
        private set
    var isListening = false
        private set

    var onResult: ((text: String) -> Unit)? = null
    var onListeningChanged: ((listening: Boolean) -> Unit)? = null

    // 메인 스레드에서 호출해야 함
    fun init(context: Context) {
        if (recognizer != null) return
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.w(TAG, "SpeechRecognizer 미지원")
            return
        }
        recognizer = SpeechRecognizer.createSpeechRecognizer(context.applicationContext)
        recognizer?.setRecognitionListener(listener)
        isReady = true
        Log.d(TAG, "STT 준비 완료")
    }

    fun toggleListening() {
        if (!isReady) { Log.d(TAG, "STT 미준비"); return }
        if (isListening) stopListening() else startListening()
    }

    private fun startListening() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ko-KR")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        }
        recognizer?.startListening(intent)
        isListening = true
        onListeningChanged?.invoke(true)
        Log.d(TAG, "STT 시작")
    }

    private fun stopListening() {
        recognizer?.stopListening()
        isListening = false
        onListeningChanged?.invoke(false)
        Log.d(TAG, "STT 중지")
    }

    fun release() {
        recognizer?.destroy()
        recognizer = null
        isReady = false
        isListening = false
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { Log.d(TAG, "onReadyForSpeech") }
        override fun onBeginningOfSpeech() { Log.d(TAG, "onBeginningOfSpeech") }
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.d(TAG, "onEndOfSpeech")
            isListening = false
            onListeningChanged?.invoke(false)
        }

        override fun onError(error: Int) {
            Log.w(TAG, "STT 오류: $error")
            isListening = false
            onListeningChanged?.invoke(false)
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val text = matches?.firstOrNull() ?: return
            if (text.isNotBlank()) {
                Log.d(TAG, "STT 결과: \"$text\"")
                onResult?.invoke(text)
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {}
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
