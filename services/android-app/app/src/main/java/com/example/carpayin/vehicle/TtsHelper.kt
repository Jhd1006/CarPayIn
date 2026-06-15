package com.example.carpayin.vehicle

import android.content.Context
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import java.util.Locale

object TtsHelper {

    private const val TAG = "TtsHelper"
    private var tts: TextToSpeech? = null
    private var isReady = false
    private var mediaPlayer: MediaPlayer? = null
    private var appContext: Context? = null

    fun init(context: Context) {
        appContext = context.applicationContext
        if (tts != null) return
        tts = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.setLanguage(Locale.KOREAN)
                isReady = true
                Log.d(TAG, "TTS 준비 완료 (폴백용)")
            }
        }
    }

    // MP3 번들 파일 재생 (고품질 데모용)
    fun playRaw(resId: Int, onDone: (() -> Unit)? = null) {
        val ctx = appContext ?: run { onDone?.invoke(); return }
        mediaPlayer?.release()
        try {
            mediaPlayer = MediaPlayer.create(ctx, resId)?.also { mp ->
                mp.setOnCompletionListener { it.release(); mediaPlayer = null; onDone?.invoke() }
                mp.setOnErrorListener { it, _, _ -> it.release(); mediaPlayer = null; onDone?.invoke(); true }
                mp.start()
                Log.d(TAG, "MP3 재생: resId=$resId")
            }
            if (mediaPlayer == null) onDone?.invoke()
        } catch (e: Exception) {
            Log.w(TAG, "MP3 재생 실패: ${e.message}")
            onDone?.invoke()
        }
    }

    // MP3 없을 때 폴백용 TTS
    fun speak(text: String, onDone: (() -> Unit)? = null) {
        if (!isReady) { Log.d(TAG, "TTS 미준비"); onDone?.invoke(); return }
        if (onDone != null) {
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String?) {}
                override fun onDone(id: String?) { onDone() }
                override fun onError(id: String?) { onDone() }
            })
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "utt")
        } else {
            tts?.speak(text, TextToSpeech.QUEUE_ADD, null, null)
        }
        Log.d(TAG, "TTS speak (폴백): $text")
    }

    fun stop() {
        mediaPlayer?.stop(); mediaPlayer?.release(); mediaPlayer = null
        tts?.stop()
    }

    fun release() {
        mediaPlayer?.release(); mediaPlayer = null
        tts?.stop(); tts?.shutdown(); tts = null
        isReady = false
    }
}
