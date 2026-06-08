package com.example.carpayin.vehicle

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log

/**
 * Pleos 우측 패널 소유권 관리 + 내비게이션 목적지 설정.
 *
 * ─ 왜 패널 소유권이 필요한가 ─────────────────────────────────────────────
 *   Pleos AAOS 에뮬레이터는 우측 패널을 nav app(ai.umos.maps...)이 소유한다.
 *   nav app이 ANR→재시작 루프를 돌 때마다 새 task ID(더 높은 번호)가 생기고,
 *   InputSink는 "높은 task ID = 터치 우선순위" 규칙으로 동작해
 *   CarPayIn 화면의 모든 터치를 nav app 쪽으로 흘려버린다.
 *   takePanelControl()을 앱 시작 시 한 번 호출하면 Pleos가 CarPayIn을
 *   패널 소유자로 등록해 task ID와 무관하게 터치가 전달된다.
 *
 * ─ 사용 흐름 ─────────────────────────────────────────────────────────────
 *   1. NaviHelper.takePanelControl(context)  — MainActivity.onCreate
 *   2. NaviHelper.init(context)              — 내비 SDK 초기화 (선택)
 *   3. NaviHelper.setDestination(...)        — 주차장 탭 시
 *   4. NaviHelper.releasePanelControl()      — MainActivity.onDestroy
 */
object NaviHelper {

    private const val TAG = "NaviHelper"

    // Pleos NaviHelper SDK 실제 클래스 (공식 패키지)
    private const val NAVI_CLASS = "ai.pleos.playground.navi.helper.NaviHelper"

    // 패널 소유권 관리 (동일 SDK, 구분을 위해 별칭 유지)
    private const val OFFICIAL_CLASS = NAVI_CLASS

    private var naviInstance: Any? = null
    private var isInitialized = false

    private var panelInstance: Any? = null
    private var isPanelControlActive = false

    var onNavigationStarted: ((lotName: String, lat: Double, lng: Double) -> Unit)? = null
    var onNavigationEnded: (() -> Unit)? = null

    // ── 패널 소유권 ───────────────────────────────────────────────────────────

    /**
     * Pleos 우측 패널 입력을 CarPayIn으로 가져온다.
     * 앱 시작 시 한 번만 호출 — 절대 반복 호출하지 말 것.
     */
    fun takePanelControl(context: Context) {
        if (isPanelControlActive) return
        val appCtx = context.applicationContext
        // 1차: 공식 helper 클래스 (ai.pleos.playground.navi.helper.NaviHelper)
        if (tryTakePanelControl(appCtx, OFFICIAL_CLASS)) return
        // 2차: 라우팅 클래스 동일 인스턴스에서 패널 소유 메서드 탐색
        tryTakePanelControl(appCtx, NAVI_CLASS)
    }

    private fun tryTakePanelControl(appCtx: Context, className: String): Boolean {
        try {
            val clazz = Class.forName(className)
            val ctor  = clazz.getConstructor(Context::class.java)
            val inst  = ctor.newInstance(appCtx)
            // initialize() no-arg 먼저, 없으면 initialize(Context) 시도
            val invoked = runCatching { clazz.getMethod("initialize").invoke(inst); true }.getOrElse {
                runCatching { clazz.getMethod("initialize", Context::class.java).invoke(inst, appCtx); true }.getOrDefault(false)
            }
            if (invoked) {
                panelInstance = inst
                isPanelControlActive = true
                Log.d(TAG, "Panel control taken via $className")
                return true
            }
        } catch (e: ClassNotFoundException) {
            Log.d(TAG, "$className not found — skipping")
        } catch (e: Exception) {
            Log.w(TAG, "takePanelControl($className) failed: ${e.message}")
        }
        return false
    }

    /**
     * onResume 등에서 내비 앱 재시작 후 패널 소유권을 강제 재취득할 때 사용.
     */
    fun reacquirePanelControl(context: Context) {
        isPanelControlActive = false
        panelInstance = null
        takePanelControl(context)
    }

    /**
     * 패널 소유권 반납. 앱 완전 종료(onDestroy) 시 한 번만 호출.
     */
    fun releasePanelControl() {
        if (!isPanelControlActive) return
        try {
            panelInstance?.let { inst ->
                inst.javaClass.getMethod("release").invoke(inst)
            }
            Log.d(TAG, "Panel control released")
        } catch (e: Exception) {
            Log.w(TAG, "releasePanelControl failed: ${e.message}")
        }
        panelInstance = null
        isPanelControlActive = false
    }

    // ── 내비게이션 SDK 초기화 ─────────────────────────────────────────────────

    fun init(context: Context) {
        if (isInitialized) return
        try {
            val clazz = Class.forName(NAVI_CLASS)
            // SDK는 getInstance(Context) 정적 메서드가 아닌 생성자(Context)를 사용
            val ctor = clazz.getConstructor(Context::class.java)
            naviInstance = ctor.newInstance(context.applicationContext)
            clazz.getMethod("initialize").invoke(naviInstance)
            registerRouteCallback()
            isInitialized = true
            Log.d(TAG, "NaviHelper SDK 초기화 성공")
            // ── SDK 메서드 목록 덤프 (목적지 설정 API 탐색용) ──────────────────
            naviInstance?.javaClass?.declaredMethods
                ?.sortedBy { it.name }
                ?.forEach { m ->
                    val params = m.parameterTypes.joinToString(", ") { it.simpleName }
                    Log.d(TAG, "SDK method: ${m.name}($params)")
                }
        } catch (e: ClassNotFoundException) {
            Log.w(TAG, "NaviHelper SDK 없음 — Pleos Connect 에뮬레이터에서만 동작")
        } catch (e: Exception) {
            Log.w(TAG, "NaviHelper init 실패: ${e.message}")
        }
    }

    // ── 목적지 설정 ───────────────────────────────────────────────────────────

    fun setDestination(
        context: Context,
        lat: Double,
        lng: Double,
        lotName: String,
        lotId: String
    ): Boolean {
        // tryAaosNavigationIntent 폴백은 사용하지 않는다.
        // 외부 앱(Google Maps 등)을 FLAG_ACTIVITY_NEW_TASK로 실행하면
        // 해당 앱의 task ID가 CarPayIn보다 높아져 패널 터치 소유권이 탈취된다.
        // Pleos SDK 내비가 실패하면 에러를 반환하고 UI에서 토스트로 처리한다.
        val started = tryPleosSdk(lat, lng, lotName)
        if (started) {
            onNavigationStarted?.invoke(lotName, lat, lng)
            GeofenceManager.onNaviDestinationChanged(lotName, lat, lng)
        }
        return started
    }

    fun cancelNavigation() {
        try {
            naviInstance?.let { navi ->
                navi.javaClass.getMethod("stopNavigation").invoke(navi)
            }
        } catch (e: Exception) {
            Log.w(TAG, "cancelNavigation 실패: ${e.message}")
        }
        onNavigationEnded?.invoke()
    }

    // ── 내부 ──────────────────────────────────────────────────────────────────

    private fun tryPleosSdk(lat: Double, lng: Double, poiName: String): Boolean {
        val navi = naviInstance ?: return false
        val candidates = listOf(
            Triple("setDestination",  arrayOf(Double::class.java, Double::class.java, String::class.java), arrayOf<Any>(lat, lng, poiName)),
            Triple("setDestination",  arrayOf(Float::class.java,  Float::class.java,  String::class.java), arrayOf<Any>(lat.toFloat(), lng.toFloat(), poiName)),
            Triple("navigate",        arrayOf(Double::class.java, Double::class.java, String::class.java), arrayOf<Any>(lat, lng, poiName)),
            Triple("startNavigation", arrayOf(Double::class.java, Double::class.java, String::class.java), arrayOf<Any>(lat, lng, poiName))
        )
        for ((name, types, args) in candidates) {
            try {
                navi.javaClass.getMethod(name, *types).invoke(navi, *args)
                try { navi.javaClass.getMethod("startNavigation").invoke(navi) } catch (_: NoSuchMethodException) {}
                return true
            } catch (_: NoSuchMethodException) { continue }
              catch (e: Exception) { Log.w(TAG, "$name 실패: ${e.message}") }
        }
        return false
    }

    private fun tryAaosNavigationIntent(context: Context, lat: Double, lng: Double, poiName: String): Boolean {
        for (uri in listOf("google.navigation:q=$lat,$lng", "geo:$lat,$lng?q=$lat,$lng(${Uri.encode(poiName)})")) {
            try {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri)).apply { addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) })
                return true
            } catch (_: ActivityNotFoundException) {}
              catch (e: Exception) { Log.w(TAG, "intent 실패: ${e.message}") }
        }
        return false
    }

    private fun registerRouteCallback() {
        val navi = naviInstance ?: return
        try {
            val listenerClass = Class.forName("$NAVI_CLASS\$OnRouteStartedListener")
            val proxy = java.lang.reflect.Proxy.newProxyInstance(
                listenerClass.classLoader, arrayOf(listenerClass)
            ) { _, method, _ ->
                when (method.name) {
                    "onNavigationEnded", "onArrived" -> onNavigationEnded?.invoke()
                }
                null
            }
            navi.javaClass.getMethod("setOnRouteStartedListener", listenerClass).invoke(navi, proxy)
        } catch (e: Exception) {
            Log.d(TAG, "경로 콜백 등록 스킵: ${e.message}")
        }
    }

    fun release() {
        try { naviInstance?.javaClass?.getMethod("release")?.invoke(naviInstance) } catch (_: Exception) {}
        naviInstance        = null
        isInitialized       = false
        onNavigationStarted = null
        onNavigationEnded   = null
    }
}
