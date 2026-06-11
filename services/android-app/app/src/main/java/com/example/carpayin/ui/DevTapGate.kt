package com.example.carpayin.ui

import android.app.Activity
import android.view.View

object DevTapGate {

    fun install(activity: Activity, target: View, onUnlocked: () -> Unit) {
        target.isClickable = true
        target.isFocusable = true
        target.setOnClickListener { onUnlocked() }
    }
}
