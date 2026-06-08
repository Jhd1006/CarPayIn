package com.example.carpayin.ui

import android.app.Activity
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.widget.EditText
import android.widget.Toast

object DevTapGate {
    private const val TAP_TARGET = 5
    private const val TAP_WINDOW_MS = 3_000L
    private const val DEV_PIN = "1234"

    fun install(activity: Activity, target: View, onUnlocked: () -> Unit) {
        val handler = Handler(Looper.getMainLooper())
        val resetTapCount = intArrayOf(0)
        val resetRunnable = Runnable { resetTapCount[0] = 0 }

        target.isClickable = true
        target.isFocusable = true
        target.setOnClickListener {
            handler.removeCallbacks(resetRunnable)
            resetTapCount[0] += 1
            if (resetTapCount[0] >= TAP_TARGET) {
                resetTapCount[0] = 0
                onUnlocked()
            } else {
                handler.postDelayed(resetRunnable, TAP_WINDOW_MS)
            }
        }
    }

    private fun showPinDialog(activity: Activity, onUnlocked: () -> Unit) {
        val input = EditText(activity).apply {
            hint = "PIN 입력"
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
        }
        android.app.AlertDialog.Builder(activity)
            .setTitle("개발자 모드")
            .setView(input)
            .setPositiveButton("확인") { _, _ ->
                if (input.text.toString() == DEV_PIN) {
                    onUnlocked()
                } else {
                    Toast.makeText(activity, "PIN 오류", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }
}
