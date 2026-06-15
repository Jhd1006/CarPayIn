package com.example.carpayin.ui

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import com.example.carpayin.R
import com.example.carpayin.config.AppConfig
import com.example.carpayin.data.ParkingStateManager
import com.example.carpayin.network.ApiManager
import com.example.carpayin.network.SessionExpiredException

class CardRegistrationActivity : Activity() {

    private val TAG = "CardRegActivity"
    private val handler = Handler(Looper.getMainLooper())

    private var webView: WebView? = null
    private lateinit var webViewContainer: android.widget.FrameLayout
    private lateinit var progressBar: ProgressBar
    private lateinit var tvStatus: TextView
    private lateinit var tvStepIndicator: TextView
    private lateinit var headerLogoTapArea: View
    private lateinit var btnCancel: TextView
    private lateinit var btnPrevStep: TextView

    private lateinit var layoutConsent: LinearLayout
    private lateinit var btnConsentAgree: Button

    private lateinit var layoutPlateInput: LinearLayout
    private lateinit var etPlateNumber: EditText
    private lateinit var btnPlateNext: Button
    private lateinit var btnTestPlate: Button

    private lateinit var layoutBrandSelect: LinearLayout
    private lateinit var brandGrid: LinearLayout

    private lateinit var accessToken: String
    private lateinit var userName: String
    private var selectedBrandName: String = ""
    private var isDevMenuVisible = false

    companion object {
        const val EXTRA_ACCESS_TOKEN = "extra_access_token"
        const val EXTRA_USER_NAME    = "extra_user_name"

        /**
         * 한국 표준형 번호판 정규식.
         *  - 12가3456    (2자리 + 한글 + 4자리, 7자)
         *  - 123가4567   (3자리 + 한글 + 4자리, 8자)
         * 지역명 prefix(예: 서울12가3456) 등 구형 포맷은 받지 않는다.
         * 사용자 직접 입력이라 형식만으로는 실재성 검증 불가 →
         * 백엔드에서 `(plate ↔ car_id)` 1:1 unique 제약으로 도용을 추가 차단한다.
         */
        val PLATE_REGEX = Regex("^\\d{2,3}[가-힣]\\d{4}$")
    }

    data class BrandInfo(
        val name: String,
        val shortName: String,
        val logoText: String,
        val logoResId: Int?,
        val bgColor: Int,
        val textColor: Int,
        val network: String
    )

    private val BRANDS = listOf(
        BrandInfo("현대카드", "HYUNDAI", "현대", R.drawable.card_logo_hyundai, 0xFF3182F6.toInt(), 0xFFFFFFFF.toInt(), "VISA"),
        BrandInfo("KB국민",   "KB",      "KB",   R.drawable.card_logo_kb,      0xFFFFCC00.toInt(), 0xFF3A2A00.toInt(), "MASTER"),
        BrandInfo("신한카드", "SHINHAN", "신한", R.drawable.card_logo_shinhan, 0xFF2563EB.toInt(), 0xFFFFFFFF.toInt(), "VISA"),
        BrandInfo("삼성카드", "SAMSUNG", "삼성", R.drawable.card_logo_samsung,  0xFF0F4CBB.toInt(), 0xFFFFFFFF.toInt(), "MASTER"),
        BrandInfo("롯데카드", "LOTTE",   "LOTTE",R.drawable.card_logo_lotte,   0xFFE11D48.toInt(), 0xFFFFFFFF.toInt(), "VISA"),
        BrandInfo("우리카드", "WOORI",   "우리", R.drawable.card_logo_woori,   0xFF0EA5E9.toInt(), 0xFFFFFFFF.toInt(), "MASTER"),
        BrandInfo("하나카드", "HANA",    "하나", R.drawable.card_logo_hana,    0xFF0F8F68.toInt(), 0xFFFFFFFF.toInt(), "VISA"),
    )

    private enum class Step { CONSENT, PLATE, BRAND, WEBVIEW }
    private var currentStep = Step.CONSENT

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_card_registration)

        webViewContainer  = findViewById(R.id.webViewContainer)
        progressBar       = findViewById(R.id.progressBarCard)
        tvStatus          = findViewById(R.id.tvCardStatus)
        tvStepIndicator   = findViewById(R.id.tvStepIndicator)
        headerLogoTapArea = findViewById(R.id.cardHeaderLogoTapArea)
        headerLogoTapArea.setOnClickListener { openDevMenu() }
        btnCancel         = findViewById(R.id.btnCancelCard)
        btnPrevStep       = findViewById(R.id.btnPrevStep)
        layoutConsent     = findViewById(R.id.layoutConsent)
        btnConsentAgree   = findViewById(R.id.btnConsentAgree)
        layoutPlateInput  = findViewById(R.id.layoutPlateInput)
        etPlateNumber     = findViewById(R.id.etPlateNumber)
        btnPlateNext      = findViewById(R.id.btnPlateNext)
        btnTestPlate      = findViewById(R.id.btnTestPlate)
        layoutBrandSelect = findViewById(R.id.layoutBrandSelect)
        brandGrid         = findViewById(R.id.brandGrid)

        accessToken = intent.getStringExtra(EXTRA_ACCESS_TOKEN) ?: ""
        userName    = intent.getStringExtra(EXTRA_USER_NAME)    ?: "고객"

        // 헤더 영역 터치는 dispatchTouchEvent에서 직접 처리한다.

        val savedPlate = ParkingStateManager.getPlateNumber(this)
        if (!savedPlate.isNullOrEmpty()) {
            etPlateNumber.setText(savedPlate)
        }

        // 번호판 입력 여부에 따라 "다음" 버튼 활성/비활성
        etPlateNumber.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) {
                btnPlateNext.isEnabled = s?.toString()?.trim()?.isNotEmpty() == true
                btnPlateNext.alpha = if (btnPlateNext.isEnabled) 1.0f else 0.45f
            }
        })
        // 초기 상태 설정
        btnPlateNext.isEnabled = !savedPlate.isNullOrEmpty()
        btnPlateNext.alpha = if (btnPlateNext.isEnabled) 1.0f else 0.45f

        btnCancel.setOnClickListener {
            Log.d(TAG, "btnCancel (처음으로) clicked at step=$currentStep")
            returnToOAuthPending()
        }

        btnPrevStep.setOnClickListener {
            // 한 단계만 되돌아감 — onBackPressed() 와 동일한 동작을 재사용
            goPrevStep()
        }

        btnConsentAgree.setOnClickListener { goToStep(Step.PLATE) }

        btnTestPlate.setOnClickListener {
            etPlateNumber.setText("123가4567")
            etPlateNumber.setSelection(etPlateNumber.text.length)
        }

        btnPlateNext.setOnClickListener {
            // 공백/하이픈/점 등 구분자 제거 + NFC 정규화(AAOS IME가 NFD로 입력할 수 있음)
            val raw   = etPlateNumber.text.toString()
            val plate = java.text.Normalizer
                .normalize(raw.replace("\\s|-|\\.|·".toRegex(), ""), java.text.Normalizer.Form.NFC)

            if (!PLATE_REGEX.matches(plate)) {
                showAaosMessageDialog(
                    title   = "번호판 형식 오류",
                    message = "번호판 형식이 올바르지 않습니다.\n\n예) 12가3456  또는  123가4567\n\n입력값: \"$plate\""
                ) { etPlateNumber.requestFocus() }
                return@setOnClickListener
            }
            if (raw != plate) etPlateNumber.setText(plate)

            hideKeyboard()
            ParkingStateManager.savePlateNumber(this, plate)
            goToStep(Step.BRAND)
        }

        buildBrandGrid()

        // 시작은 무조건 Step 0(동의)부터
        goToStep(Step.CONSENT)
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        if (!isDevMenuVisible && DevLogoTapTarget.consumeTap(ev, headerLogoTapArea) {
            openDevMenu()
        }) {
            return true
        }
        return super.dispatchTouchEvent(ev)
    }

    private fun openDevMenu() {
        if (isDevMenuVisible) return
        isDevMenuVisible = true
        val decorView = window.decorView as android.widget.FrameLayout

        val overlay = android.widget.FrameLayout(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(0xAA000000.toInt())
            elevation = 999f
        }
        fun dismissOverlay() {
            runOnUiThread {
                isDevMenuVisible = false
                decorView.removeView(overlay)
            }
        }

        val card = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            background = roundedBackground(0xFFFFFFFF.toInt())
            val lp = android.widget.FrameLayout.LayoutParams(
                (resources.displayMetrics.widthPixels * 0.78).toInt(),
                (resources.displayMetrics.heightPixels * 0.65).toInt()
            )
            lp.gravity = android.view.Gravity.CENTER
            layoutParams = lp
        }

        card.addView(android.widget.TextView(this).apply {
            text = "개발자 메뉴"
            setTextColor(0xFF191F28.toInt()); textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            setPadding(dp(20), dp(16), dp(20), dp(8))
        })

        val container = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(dp(12), dp(4), dp(12), dp(4))
        }

        fun addBtn(label: String, action: () -> Unit) {
            container.addView(android.widget.Button(this).apply {
                text = label; textSize = 13f
                setTextColor(0xFF191F28.toInt())
                background = roundedBackground(0xFFF4F7FB.toInt(), 0xFFDCE5F0.toInt())
                setPadding(dp(16), dp(12), dp(16), dp(12))
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
                ).also { it.setMargins(0, 0, 0, dp(6)) }
                setOnClickListener { dismissOverlay(); action() }
            })
        }

        addBtn("테스트 번호판 자동입력 (123가4567)") {
            val testPlate = "123가4567"
            etPlateNumber.setText(testPlate)
            ParkingStateManager.savePlateNumber(this, testPlate)
            android.widget.Toast.makeText(this, "번호판 설정: $testPlate", android.widget.Toast.LENGTH_SHORT).show()
        }
        addBtn("번호판 직접 입력") {
            val et = android.widget.EditText(this).apply {
                hint = "예) 12가3456"; inputType = android.text.InputType.TYPE_CLASS_TEXT
                val saved = ParkingStateManager.getPlateNumber(this@CardRegistrationActivity)
                if (!saved.isNullOrBlank()) setText(saved)
            }
            showAaosInputDialog("번호판 직접 입력", et) {
                val plate = java.text.Normalizer.normalize(
                    et.text.toString().replace("\\s|-|\\.|·".toRegex(), ""),
                    java.text.Normalizer.Form.NFC
                )
                if (plate.isNotBlank()) {
                    etPlateNumber.setText(plate)
                    ParkingStateManager.savePlateNumber(this, plate)
                }
            }
        }
        addBtn("PLATE 단계 건너뛰기 (현재 입력값 또는 테스트 번호판 사용)") {
            val raw = etPlateNumber.text.toString().trim().ifBlank { "123가4567" }
            val plate = java.text.Normalizer.normalize(
                raw.replace("\\s|-|\\.|·".toRegex(), ""),
                java.text.Normalizer.Form.NFC
            )
            etPlateNumber.setText(plate)
            ParkingStateManager.savePlateNumber(this, plate)
            goToStep(Step.BRAND)
        }

        card.addView(android.widget.ScrollView(this).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
            )
            addView(container)
        })
        card.addView(android.widget.Button(this).apply {
            text = "닫기"; textSize = 14f; setTextColor(0xFF1B64DA.toInt())
            setBackgroundColor(android.graphics.Color.TRANSPARENT); minHeight = dp(48)
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.setMargins(dp(12), 0, dp(12), dp(8)) }
            setOnClickListener { dismissOverlay() }
        })

        overlay.addView(card)
        overlay.setOnClickListener { dismissOverlay() }
        card.setOnClickListener { }
        decorView.addView(overlay)
    }

    /** AlertDialog 대신 decorView overlay 사용 — AAOS 패널 소유권 유지 */
    private fun showAaosMessageDialog(title: String, message: String, onConfirm: () -> Unit = {}) {
        val decorView = window.decorView as android.widget.FrameLayout
        val overlay = android.widget.FrameLayout(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(0xAA000000.toInt()); elevation = 1000f
        }
        fun dismiss() { runOnUiThread { decorView.removeView(overlay) } }

        val card = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            background = roundedBackground(0xFFFFFFFF.toInt())
            setPadding(dp(24), dp(20), dp(24), dp(8))
            val lp = android.widget.FrameLayout.LayoutParams(
                (resources.displayMetrics.widthPixels * 0.72).toInt(),
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.gravity = android.view.Gravity.CENTER; layoutParams = lp
        }
        card.addView(android.widget.TextView(this).apply {
            text = title; setTextColor(0xFF191F28.toInt()); textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = dp(10) }
        })
        card.addView(android.widget.TextView(this).apply {
            text = message; setTextColor(0xFF4E5968.toInt()); textSize = 14f
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = dp(8) }
        })
        card.addView(android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.END
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            addView(android.widget.Button(this@CardRegistrationActivity).apply {
                text = "확인"; textSize = 14f; setTextColor(0xFF1B64DA.toInt())
                setBackgroundColor(android.graphics.Color.TRANSPARENT); minHeight = dp(48)
                setPadding(dp(8), 0, dp(8), 0)
                setOnClickListener { dismiss(); onConfirm() }
            })
        })
        overlay.addView(card)
        overlay.setOnClickListener { dismiss(); onConfirm() }
        card.setOnClickListener { }
        decorView.addView(overlay)
    }

    private fun showAaosInputDialog(title: String, inputView: android.view.View, onSave: () -> Unit) {
        val decorView = window.decorView as android.widget.FrameLayout

        val overlay = android.widget.FrameLayout(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(0xAA000000.toInt())
            elevation = 1000f
        }
        fun dismiss() { runOnUiThread { decorView.removeView(overlay) } }

        val card = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            background = roundedBackground(0xFFFFFFFF.toInt())
            setPadding(dp(24), dp(20), dp(24), dp(8))
            val lp = android.widget.FrameLayout.LayoutParams(
                (resources.displayMetrics.widthPixels * 0.72).toInt(),
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.gravity = android.view.Gravity.CENTER
            layoutParams = lp
        }
        card.addView(android.widget.TextView(this).apply {
            text = title; setTextColor(0xFF191F28.toInt()); textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.bottomMargin = dp(12) }
        })
        card.addView(inputView, android.widget.LinearLayout.LayoutParams(
            android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
            android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
        ).also { it.bottomMargin = dp(8) })
        card.addView(android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.END
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            addView(android.widget.Button(this@CardRegistrationActivity).apply {
                text = "취소"; textSize = 14f; setTextColor(android.graphics.Color.BLACK)
                setBackgroundColor(android.graphics.Color.TRANSPARENT); minHeight = dp(48)
                setPadding(dp(8), 0, dp(8), 0)
                setOnClickListener { dismiss() }
            })
            addView(android.widget.Button(this@CardRegistrationActivity).apply {
                text = "저장"; textSize = 14f; setTextColor(0xFF1B64DA.toInt())
                setBackgroundColor(android.graphics.Color.TRANSPARENT); minHeight = dp(48)
                setPadding(dp(8), 0, dp(8), 0)
                setOnClickListener { dismiss(); onSave() }
            })
        })
        overlay.addView(card)
        overlay.setOnClickListener { dismiss() }
        card.setOnClickListener { }
        decorView.addView(overlay)
    }

    private fun roundedBackground(
        fillColor: Int,
        strokeColor: Int? = null
    ): android.graphics.drawable.GradientDrawable {
        return android.graphics.drawable.GradientDrawable().apply {
            setColor(fillColor)
            cornerRadius = dp(8).toFloat()
            strokeColor?.let { setStroke(dp(1), it) }
        }
    }

    private fun goToStep(step: Step) {
        currentStep = step
        layoutConsent.visibility     = View.GONE
        layoutPlateInput.visibility  = View.GONE
        layoutBrandSelect.visibility = View.GONE
        webViewContainer.visibility  = View.GONE
        progressBar.visibility       = View.GONE

        when (step) {
            Step.CONSENT -> {
                layoutConsent.visibility = View.VISIBLE
                tvStatus.text        = "개인정보 동의"
                tvStepIndicator.text = "1 / 4"
            }
            Step.PLATE -> {
                layoutPlateInput.visibility = View.VISIBLE
                tvStatus.text        = "번호판 입력"
                tvStepIndicator.text = "2 / 4"
            }
            Step.BRAND -> {
                layoutBrandSelect.visibility = View.VISIBLE
                tvStatus.text        = "카드사 선택"
                tvStepIndicator.text = "3 / 4"
            }
            Step.WEBVIEW -> {
                setupWebView()
                webViewContainer.visibility = View.INVISIBLE
                progressBar.visibility = View.VISIBLE
                tvStatus.text        = "카드 정보 입력"
                tvStepIndicator.text = "4 / 4"
            }
        }

        // 첫 단계(CONSENT)에서는 '이전'이 의미 없으므로 숨기고,
        // 그 외 단계에서는 헤더에 '← 이전' 버튼을 노출한다.
        btnPrevStep.visibility = if (step == Step.CONSENT) View.GONE else View.VISIBLE
    }

    /**
     * '← 이전' / 시스템 백 버튼 공통 처리.
     * 단계에 맞춰 한 단계만 되돌아간다. WEBVIEW 단계에서는 WebView 의
     * 내부 히스토리가 있으면 그쪽을 먼저 소비한다.
     */
    private fun goPrevStep() {
        when (currentStep) {
            Step.CONSENT -> returnToOAuthPending()  // 첫 단계에서는 '처음으로'와 동일
            Step.PLATE   -> goToStep(Step.CONSENT)
            Step.BRAND   -> goToStep(Step.PLATE)
            Step.WEBVIEW -> {
                if (webView?.canGoBack() == true) webView?.goBack() else goToStep(Step.BRAND)
            }
        }
    }

    private fun buildBrandGrid() {
        brandGrid.removeAllViews()
        val rows = BRANDS.chunked(2)
        rows.forEach { rowBrands ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).also { it.setMargins(0, 0, 0, dp(12)) }
            }
            rowBrands.forEachIndexed { index, brand -> row.addView(makeBrandCard(brand, index < rowBrands.lastIndex)) }
            if (rowBrands.size == 1) {
                row.addView(View(this).apply { layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) })
            }
            brandGrid.addView(row)
        }
    }

    private fun makeBrandCard(brand: BrandInfo, hasRightMargin: Boolean): View {
        val baseDrawable = android.graphics.drawable.GradientDrawable().apply {
            setColor(0xFFFFFFFF.toInt())
            cornerRadius = dp(8).toFloat()
            setStroke(dp(1), 0xFFE4EAF2.toInt())
        }
        val rippleDrawable = android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(0x22000000),
            baseDrawable,
            null
        )
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity     = Gravity.CENTER_VERTICAL
            background  = rippleDrawable
            isClickable = true  // RippleDrawable은 clickable이어야 ripple이 트리거됨
            isFocusable = true
            layoutParams = LinearLayout.LayoutParams(0, dp(72), 1f).also {
                it.setMargins(0, 0, if (hasRightMargin) dp(10) else 0, 0)
            }
            setPadding(dp(10), dp(10), dp(10), dp(10))
        }

        val logo = makeBrandLogoView(brand)

        val textColumn = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }

        val tvName = TextView(this).apply {
            text = brand.name
            setTextColor(0xFF191F28.toInt())
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            maxLines = 1
        }
        val tvMeta = TextView(this).apply {
            text = "${brand.shortName} · ${brand.network}"
            setTextColor(0xFF6B7684.toInt())
            textSize = 10f
            maxLines = 1
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).also { it.topMargin = dp(2) }
        }

        textColumn.addView(tvName)
        textColumn.addView(tvMeta)
        card.addView(logo)
        card.addView(textColumn)
        card.setOnClickListener { onBrandSelected(brand) }
        return card
    }

    private fun makeBrandLogoView(brand: BrandInfo): View {
        val params = LinearLayout.LayoutParams(dp(62), dp(44)).also { it.rightMargin = dp(10) }
        val logoBackground = android.graphics.drawable.GradientDrawable().apply {
            setColor(0xFFF7F9FC.toInt())
            cornerRadius = dp(8).toFloat()
            setStroke(dp(1), 0xFFE4EAF2.toInt())
        }
        return if (brand.logoResId != null) {
            ImageView(this).apply {
                setImageResource(brand.logoResId)
                scaleType = ImageView.ScaleType.FIT_CENTER
                background = logoBackground
                setPadding(dp(5), dp(5), dp(5), dp(5))
                layoutParams = params
            }
        } else {
            TextView(this).apply {
                text = brand.logoText
                setTextColor(brand.textColor)
                textSize = if (brand.logoText.length > 3) 10f else 12f
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                gravity = Gravity.CENTER
                background = android.graphics.drawable.GradientDrawable().apply {
                    setColor(brand.bgColor)
                    cornerRadius = dp(8).toFloat()
                }
                layoutParams = params
            }
        }
    }

    private fun onBrandSelected(brand: BrandInfo) {
        selectedBrandName = brand.name
        tvStatus.text = "${brand.name} 결제창 불러오는 중..."
        goToStep(Step.WEBVIEW)
        loadCardRegistrationPage(brand)
    }

    private var webViewReady = false

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        if (webViewReady) return
        webViewReady = true

        val wv = WebView(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                android.widget.FrameLayout.LayoutParams.MATCH_PARENT
            )
            settings.apply {
                javaScriptEnabled    = true
                domStorageEnabled    = true
                loadWithOverviewMode = true
                useWideViewPort      = true
            }
            setBackgroundColor(Color.TRANSPARENT)
            isVerticalScrollBarEnabled = false
            addJavascriptInterface(PgJsInterface(), "Android")
            webViewClient = object : WebViewClient() {
                override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                    progressBar.visibility = View.VISIBLE
                }
                override fun onPageFinished(view: WebView?, url: String?) {
                    progressBar.visibility = View.GONE
                    webViewContainer.visibility = View.VISIBLE
                }
                override fun onReceivedError(view: WebView?, errorCode: Int, description: String?, failingUrl: String?) {
                    handler.post {
                        Toast.makeText(this@CardRegistrationActivity, "페이지 로딩 실패. 서버를 확인해 주세요.", Toast.LENGTH_LONG).show()
                        goToStep(Step.BRAND)
                    }
                }
                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                    if (request?.isForMainFrame != true) return
                    Log.e(TAG, "WebView load failed: ${error?.description} url=${request.url}")
                    handler.post {
                        Toast.makeText(this@CardRegistrationActivity, "페이지 로딩 실패: ${error?.description}", Toast.LENGTH_LONG).show()
                        goToStep(Step.BRAND)
                    }
                }
                override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, errorResponse: WebResourceResponse?) {
                    if (request?.isForMainFrame != true) return
                    Log.e(TAG, "WebView HTTP ${errorResponse?.statusCode} url=${request.url}")
                    handler.post {
                        Toast.makeText(this@CardRegistrationActivity, "PG 페이지 오류: HTTP ${errorResponse?.statusCode}", Toast.LENGTH_LONG).show()
                        goToStep(Step.BRAND)
                    }
                }
            }
            webChromeClient = WebChromeClient()
        }
        webView = wv
        webViewContainer.addView(wv)
    }

    private fun loadCardRegistrationPage(brand: BrandInfo) {
        val currentPlate = ParkingStateManager.getPlateNumber(this) ?: ""

        Thread {
            try {
                val result = ApiManager.withAutoRefresh(this) { token ->
                    ApiManager.createCardOrder(
                        plate = currentPlate,
                        bankName = brand.name,
                        agreeTerms = true,
                        accessToken = token
                    )
                }
                val fixedPgUrl = normalizePgUrlForEmulator(result.pgUrl)
                Log.d(TAG, "Loading PG url: $fixedPgUrl")
                handler.post {
                    tvStatus.text = "카드 정보 입력"
                    webView?.loadUrl(fixedPgUrl)
                }
            } catch (e: SessionExpiredException) {
                handler.post {
                    Toast.makeText(this, e.message, Toast.LENGTH_LONG).show()
                    setResult(RESULT_CANCELED)
                    finish()
                }
            } catch (e: Exception) {
                Log.e(TAG, "createCardOrder failed", e)
                val (status, friendly) = mapServerError(e.message)
                handler.post {
                    Toast.makeText(this, friendly, Toast.LENGTH_LONG).show()
                    // 형식/소유주/중복 오류는 PLATE 단계로 돌려보내 입력을 고치게 한다.
                    // 그 외 일시 오류는 카드사 선택 단계로 복귀.
                    if (status == 400 || status == 403 || status == 409) {
                        goToStep(Step.PLATE)
                    } else {
                        goToStep(Step.BRAND)
                    }
                }
            }
        }.start()
    }

    /**
     * ApiManager 가 던지는 "HTTP {code}: {body}" 메시지를 파싱해서
     * 사용자에게 보여줄 친화 메시지로 매핑한다.
     * body 가 FastAPI 표준 응답({"detail":"..."}) 이면 detail 만 추출.
     */
    private fun mapServerError(rawMessage: String?): Pair<Int, String> {
        val msg = rawMessage.orEmpty()
        val httpRegex = Regex("""HTTP\s+(\d{3}):\s*(.*)""", RegexOption.DOT_MATCHES_ALL)
        val match = httpRegex.find(msg)
        if (match == null) {
            return 0 to "카드 등록 준비 실패: ${msg.ifBlank { "알 수 없는 오류" }}"
        }
        val code = match.groupValues[1].toIntOrNull() ?: 0
        val body = match.groupValues[2].trim()
        val detail = runCatching {
            org.json.JSONObject(body).optString("detail", body)
        }.getOrDefault(body)
        val normalizedDetail = detail.lowercase()

        val friendly = when (code) {
            400 -> "번호판 형식이 올바르지 않습니다.\n예) 12가3456 또는 123가4567"
            403 -> "차량 소유주 정보와 일치하지 않습니다.\n($detail)"
            404 -> "마이현대 차량 등록을 먼저 완료해 주세요."
            409 -> when {
                normalizedDetail == "confirmed_car_required" ->
                    "마이현대 차량 연결을 먼저 완료해 주세요.\nQR을 새로고침한 뒤 다시 로그인해 주세요."
                normalizedDetail.contains("vin_hash_mismatch") ->
                    "QR 세션과 선택 차량이 일치하지 않습니다.\nQR을 새로고침한 뒤 다시 시도해 주세요."
                normalizedDetail.contains("car_id_not_in_hyundai_list") ->
                    "선택한 차량이 마이현대 차량 목록에 없습니다.\nQR을 새로고침한 뒤 다시 시도해 주세요."
                detail.isNotBlank() -> detail
                else -> "이미 등록된 번호판입니다."
            }
            else -> "카드 등록 준비 실패 (HTTP $code): ${detail.ifBlank { "서버 오류" }}"
        }
        return code to friendly
    }

    private fun normalizePgUrlForEmulator(pgUrl: String): String {
        return AppConfig.normalizeLocalhostForDevice(pgUrl)
    }

    inner class PgJsInterface {
        @JavascriptInterface
        fun onRegistrationCompleteV3(orderId: String, lastFour: String) {
            completeRegistration("", lastFour, selectedBrandName.ifBlank { "CARD" })
        }

        @JavascriptInterface
        fun onRegistrationComplete(customerKey: String, orderId: String, lastFour: String, cardBrand: String) {
            completeRegistration("", lastFour, cardBrand)
        }

        @JavascriptInterface
        fun onRegistrationCompleteV2(
            customerKey: String,
            orderId: String,
            paymentMethodId: String,
            lastFour: String,
            cardBrand: String
        ) {
            completeRegistration(paymentMethodId, lastFour, cardBrand)
        }

        private fun completeRegistration(paymentMethodId: String, lastFour: String, cardBrand: String) {
            if (paymentMethodId.isNotBlank()) {
                ParkingStateManager.savePaymentMethodId(this@CardRegistrationActivity, paymentMethodId)
            }
            ParkingStateManager.saveCardInfo(this@CardRegistrationActivity, lastFour, cardBrand)
            handler.post {
                Toast.makeText(this@CardRegistrationActivity, "$cardBrand ****$lastFour 등록 완료!\n이제 주차는 자동 결제됩니다.", Toast.LENGTH_LONG).show()
                handler.postDelayed({
                    setResult(RESULT_OK)
                    finish()
                }, 1_500)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        window.decorView.requestFocus()
    }

    override fun onBackPressed() {
        Log.d(TAG, "onBackPressed at step=$currentStep")
        goPrevStep()
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacksAndMessages(null)
        webView?.destroy()
    }

    private fun returnToOAuthPending() {
        Log.d(TAG, "returnToOAuthPending() called — stack trace:", Throwable())
        ParkingStateManager.setOAuthComplete(this, true)
        ParkingStateManager.setRegistered(this, false)
        // MainActivity.onActivityResult(101, RESULT_CANCELED) 가
        //  showOAuthPendingState() 로 화면을 복귀시켜 주므로,
        //  여기서 별도로 startActivity 를 호출하면 안 된다.
        //  (FLAG_ACTIVITY_CLEAR_TOP + startActivityForResult 와 충돌해
        //   onActivityResult 가 사라지거나 화면이 두 번 그려지는 문제가 있었다.)
        setResult(RESULT_CANCELED)
        finish()
    }

    private fun dp(value: Int): Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()

    private fun hideKeyboard() {
        val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
        currentFocus?.let { imm.hideSoftInputFromWindow(it.windowToken, 0) }
    }
}
