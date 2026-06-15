package com.example.carpayin.ui

import android.graphics.Rect
import android.view.MotionEvent
import android.view.View

object DevLogoTapTarget {

    fun consumeTap(
        event: MotionEvent,
        target: View,
        extraTouchPx: Int = 0,
        onTap: () -> Unit
    ): Boolean {
        if (event.action != MotionEvent.ACTION_UP) return false

        val bounds = Rect()
        if (!target.getGlobalVisibleRect(bounds)) return false
        if (extraTouchPx > 0) {
            bounds.inset(-extraTouchPx, -extraTouchPx)
        }

        if (!bounds.contains(event.rawX.toInt(), event.rawY.toInt())) return false
        onTap()
        return true
    }
}
