package com.example.carpayin.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.graphics.Rect
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import com.example.carpayin.R
import com.example.carpayin.data.ParkingStateManager
import com.example.carpayin.network.ApiManager
import com.example.carpayin.vehicle.VehicleDataManager
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import java.security.MessageDigest
import java.util.UUID

class RegistrationActivity : Activity() {

    private val TAG = "RegistrationActivity"
    private val handler = Handler(Looper.getMainLooper())
    private var isPolling = false

    private lateinit var ivQrCode: ImageView
    private lateinit var ivRegistrationLogo: ImageView
    private lateinit var tvPollingStatus: TextView
    private lateinit var tvSubMessage: TextView
    private lateinit var btnCancel: Button
    private lateinit var btnRefreshQr: Button
    private lateinit var progressBarReg: ProgressBar

    private lateinit var loginSessionId: String
    private lateinit var vin: String

    private val POLL_TIMEOUT_MS = 5 * 60 * 1000L
    private var pollStartTime = 0L
    private var didCompleteLogin = false
    private var didHideQrAfterAuth = false
    private var pollCount = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_registration)

        ivQrCode = findViewById(R.id.ivQrCode)
        ivRegistrationLogo = findViewById(R.id.ivRegistrationLogo)
        tvPollingStatus = findViewById(R.id.tvPollingStatus)
        tvSubMessage = findViewById(R.id.tvSubMessage)
        btnCancel = findViewById(R.id.btnCancel)
        btnRefreshQr = findViewById(R.id.btnRefreshQr)
        progressBarReg = findViewById(R.id.progressBarReg)

        vin = VehicleDataManager.readVin(this)
        loginSessionId = UUID.randomUUID().toString()

        btnCancel.setOnClickListener {
            isPolling = false
            setResult(RESULT_CANCELED)
            finish()
        }

        btnRefreshQr.setOnClickListener {
            isPolling = false
            handler.removeCallbacksAndMessages(null)
            loginSessionId = UUID.randomUUID().toString()
            didCompleteLogin = false
            didHideQrAfterAuth = false
            pollCount = 0
            ivQrCode.visibility = View.VISIBLE
            btnRefreshQr.visibility = View.VISIBLE
            btnCancel.visibility = View.VISIBLE
            ivQrCode.setImageBitmap(null)
            tvPollingStatus.text = "Scan this QR with MyHyundai"
            tvSubMessage.text = "Log in with your MyHyundai account to link a vehicle."
            renderQrCode()
            startPolling()
        }

        renderQrCode()
        startPolling()
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        if (ev.action == MotionEvent.ACTION_UP) {
            val logoBounds = Rect()
            ivRegistrationLogo.getGlobalVisibleRect(logoBounds)
            logoBounds.inset(-dp(32), -dp(32))
            if (logoBounds.contains(ev.rawX.toInt(), ev.rawY.toInt())) {
                startActivity(Intent(this, MainActivity::class.java).apply {
                    action = MainActivity.ACTION_SHOW_DEV_MENU
                    flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                    putExtra(MainActivity.EXTRA_SHOW_DEV_MENU, true)
                })
                return true
            }
        }
        return super.dispatchTouchEvent(ev)
    }

    private fun sha256(input: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(input.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun renderQrCode() {
        val vinHash = sha256(vin + loginSessionId)
        progressBarReg.visibility = View.VISIBLE
        ivQrCode.setImageBitmap(null)

        Thread {
            try {
                val authStartUrl = ApiManager.createQrSession(loginSessionId, vinHash).ifBlank {
                    "${ApiManager.QR_BASE_URL}/auth/hyundai/start?session_id=$loginSessionId"
                }
                val bits = QRCodeWriter().encode(authStartUrl, BarcodeFormat.QR_CODE, 512, 512)
                val bitmap = Bitmap.createBitmap(bits.width, bits.height, Bitmap.Config.RGB_565)
                for (x in 0 until bits.width) {
                    for (y in 0 until bits.height) {
                        bitmap.setPixel(x, y, if (bits[x, y]) Color.BLACK else Color.WHITE)
                    }
                }
                handler.post {
                    ivQrCode.setImageBitmap(bitmap)
                    progressBarReg.visibility = View.GONE
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to render QR: ${e.message}")
                handler.post {
                    progressBarReg.visibility = View.GONE
                    tvPollingStatus.text = "QR session creation failed"
                    tvSubMessage.text = e.message ?: "Check backend connection and try again."
                    btnRefreshQr.visibility = View.VISIBLE
                    btnCancel.visibility = View.VISIBLE
                }
            }
        }.start()
    }

    private fun startPolling() {
        isPolling = true
        didCompleteLogin = false
        didHideQrAfterAuth = false
        pollCount = 0
        pollStartTime = System.currentTimeMillis()
        scheduleNextPoll()
    }

    private fun scheduleNextPoll() {
        if (!isPolling || didCompleteLogin) return
        handler.postDelayed({ doPoll() }, 2_000)
    }

    private fun doPoll() {
        if (!isPolling || didCompleteLogin) return
        if (System.currentTimeMillis() - pollStartTime > POLL_TIMEOUT_MS) {
            isPolling = false
            tvPollingStatus.text = "Login timed out"
            tvSubMessage.text = "Refresh the QR and try again."
            return
        }

        Thread {
            try {
                val result = ApiManager.checkLoginSession(loginSessionId)
                if (result.isComplete) {
                    handler.post { onLoginComplete(result) }
                } else if (result.status == "authorized" || result.status == "agreement_required") {
                    handler.post {
                        showAuthorizedProgress(result.status)
                        scheduleNextPoll()
                    }
                } else if (result.status == "error" || result.status == "agreement_error") {
                    handler.post {
                        isPolling = false
                        showAuthorizedProgress(result.status)
                        tvPollingStatus.text = "MyHyundai processing failed"
                        tvSubMessage.text = result.debugMessage.ifBlank { "Refresh the QR and try again." }
                        btnRefreshQr.visibility = View.VISIBLE
                        btnCancel.visibility = View.VISIBLE
                    }
                } else {
                    handler.post {
                        pollCount += 1
                        tvPollingStatus.text = "Waiting for login... ($pollCount)"
                        if (pollCount >= 2 && result.debugMessage.isNotBlank()) {
                            tvSubMessage.text = result.debugMessage
                        }
                        scheduleNextPoll()
                    }
                }
            } catch (e: Exception) {
                handler.post {
                    pollCount += 1
                    tvPollingStatus.text = "Checking login status..."
                    tvSubMessage.text = e.message ?: "Failed to check login status"
                    scheduleNextPoll()
                }
            }
        }.start()
    }

    private fun onLoginComplete(result: ApiManager.SessionStatusResult) {
        if (didCompleteLogin) return
        didCompleteLogin = true
        isPolling = false
        handler.removeCallbacksAndMessages(null)

        ivQrCode.visibility = View.GONE
        btnCancel.visibility = View.GONE
        btnRefreshQr.visibility = View.GONE
        tvPollingStatus.text = "MyHyundai login complete"
        tvSubMessage.text = "Linking the vehicle selected in MyHyundai."

        val linkedVehicles = result.vehicleList.filter { it.carId.isNotBlank() }
        when {
            linkedVehicles.isEmpty() -> {
                didCompleteLogin = false
                btnRefreshQr.visibility = View.VISIBLE
                btnCancel.visibility = View.VISIBLE
                tvPollingStatus.text = "No Hyundai vehicle found"
                tvSubMessage.text = "No linked vehicle was returned. Check the backend vehicle-list log."
            }
            linkedVehicles.size == 1 -> {
                completeRegistration(result, linkedVehicles.first())
            }
            else -> {
                showVehiclePicker(result, linkedVehicles)
            }
        }
    }

    private fun showAuthorizedProgress(status: String = "authorized") {
        if (!didHideQrAfterAuth) {
            didHideQrAfterAuth = true
            ivQrCode.visibility = View.GONE
            btnRefreshQr.visibility = View.GONE
            btnCancel.visibility = View.GONE
        }
        tvPollingStatus.text = "MyHyundai login complete"
        tvSubMessage.text = if (status == "agreement_required") {
            "Waiting for Hyundai data agreement..."
        } else {
            "Fetching Hyundai vehicle list..."
        }
    }

    /**
     * AAOS 환경에서 AlertDialog는 별도 Window를 생성해 패널 소유권이 적용되지 않으므로
     * window.decorView에 직접 overlay를 추가해 터치 전달 문제를 우회한다.
     */
    private fun showVehiclePicker(
        result: ApiManager.SessionStatusResult,
        vehicles: List<ApiManager.VehicleInfo>
    ) {
        val decorView = window.decorView as FrameLayout

        val overlay = FrameLayout(this).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(0xAA000000.toInt())
            elevation = 999f
        }
        fun dismiss() { runOnUiThread { decorView.removeView(overlay) } }
        fun onCancel() {
            dismiss()
            didCompleteLogin = false
            btnRefreshQr.visibility = View.VISIBLE
            btnCancel.visibility = View.VISIBLE
            tvPollingStatus.text = "Vehicle selection required"
            tvSubMessage.text = "Choose the Hyundai vehicle to link with this car."
        }

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFFFFFFFF.toInt())
            setPadding(dp(20), dp(20), dp(20), dp(12))
            val lp = FrameLayout.LayoutParams(
                (resources.displayMetrics.widthPixels * 0.78).toInt(),
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.gravity = Gravity.CENTER
            layoutParams = lp
        }
        card.addView(TextView(this).apply {
            text = "CarPayIn에 연결할 차량"
            setTextColor(0xFF191F28.toInt()); textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = dp(12) }
        })

        val listContainer = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = dp(8) }
        }
        val listInner = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        vehicles.forEachIndexed { i, vehicle ->
            listInner.addView(Button(this).apply {
                text = vehicleLabel(vehicle)
                textSize = 14f; setTextColor(0xFF1B64DA.toInt())
                setBackgroundColor(Color.TRANSPARENT)
                gravity = Gravity.START or Gravity.CENTER_VERTICAL
                setPadding(dp(4), dp(8), dp(4), dp(8))
                setOnClickListener { dismiss(); completeRegistration(result, vehicles[i]) }
            })
        }
        listContainer.addView(listInner)
        card.addView(listContainer)

        card.addView(Button(this).apply {
            text = "취소"; textSize = 14f; setTextColor(Color.BLACK)
            setBackgroundColor(Color.TRANSPARENT)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.gravity = Gravity.END }
            setOnClickListener { onCancel() }
        })

        overlay.addView(card)
        overlay.setOnClickListener { onCancel() }
        card.setOnClickListener { }
        decorView.addView(overlay)
    }

    private fun dp(value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun vehicleLabel(vehicle: ApiManager.VehicleInfo): String {
        val model = vehicle.modelName.ifBlank { "Hyundai vehicle" }
        val year = if (vehicle.year > 0) " (${vehicle.year})" else ""
        val idTail = vehicle.carId.takeLast(6)
        return "$model$year - carId ...$idTail"
    }

    private fun completeRegistration(
        result: ApiManager.SessionStatusResult,
        selectedVehicle: ApiManager.VehicleInfo?
    ) {
        val selectedModel = selectedVehicle?.modelName?.ifBlank { result.modelName } ?: result.modelName
        val selectedCarId = selectedVehicle?.carId.orEmpty()

        if (selectedCarId.isBlank() || result.accessToken.isBlank()) {
            showVehicleLinkFailure("Missing vehicle confirmation data. Refresh the QR and try again.")
            return
        }

        tvPollingStatus.text = "Linking Hyundai vehicle"
        tvSubMessage.text = "Confirming that this QR session matches the selected vehicle."
        btnRefreshQr.visibility = View.GONE
        btnCancel.visibility = View.GONE

        Thread {
            runCatching {
                ApiManager.confirmCar(
                    vinHash = sha256(vin + loginSessionId),
                    carId = selectedCarId,
                    accessToken = result.accessToken
                )
            }.onSuccess {
                handler.post {
                    saveCompletedLoginState(result, it, selectedModel, selectedCarId)
                    launchOAuthPending()
                }
            }.onFailure {
                Log.w(TAG, "Failed to confirm Hyundai vehicle link: ${it.message}")
                handler.post {
                    showVehicleLinkFailure(it.message)
                }
            }
        }.start()
    }

    private fun saveCompletedLoginState(
        result: ApiManager.SessionStatusResult,
        confirmResult: ApiManager.ConfirmCarResult,
        selectedModel: String,
        selectedCarId: String
    ) {
        runCatching {
            if (confirmResult.accessToken.isNotBlank() && confirmResult.refreshToken.isNotBlank()) {
                ParkingStateManager.saveTokens(this, confirmResult.accessToken, confirmResult.refreshToken)
            }
            val plateNumber = confirmResult.plateNumber.ifBlank { result.plateNumber }
            if (plateNumber.isNotBlank()) {
                ParkingStateManager.savePlateNumber(this, plateNumber)
            }
            ParkingStateManager.saveHyundaiUserInfo(
                this,
                confirmResult.userId.ifBlank { result.userId },
                confirmResult.userName.ifBlank { result.userName },
                confirmResult.modelName.ifBlank { selectedModel },
                confirmResult.carId.ifBlank { selectedCarId }
            )
            ParkingStateManager.setOAuthComplete(this, true)
            ParkingStateManager.setRegistered(this, false)
        }.onFailure {
            Log.e(TAG, "Failed to save login state", it)
            ParkingStateManager.setOAuthComplete(this, true)
            ParkingStateManager.setRegistered(this, false)
        }
    }

    private fun launchOAuthPending() {
        handler.postDelayed({
            setResult(RESULT_OK)
            finish()
        }, 800)
    }

    private fun showVehicleLinkFailure(rawMessage: String?) {
        didCompleteLogin = false
        isPolling = false
        btnRefreshQr.visibility = View.VISIBLE
        btnCancel.visibility = View.VISIBLE
        tvPollingStatus.text = "Vehicle link failed"
        tvSubMessage.text = when {
            rawMessage.orEmpty().contains("vin_hash_mismatch") ->
                "This QR session no longer matches the vehicle. Refresh the QR and try again."
            rawMessage.orEmpty().contains("car_id_not_in_hyundai_list") ->
                "The selected vehicle was not returned by MyHyundai. Refresh the QR and try again."
            else ->
                "Refresh the QR and try again."
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isPolling = false
        handler.removeCallbacksAndMessages(null)
    }
}
