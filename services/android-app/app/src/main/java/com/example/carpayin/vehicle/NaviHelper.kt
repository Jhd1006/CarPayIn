package com.example.carpayin.vehicle

import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.RouteDriving
import ai.pleos.playground.navi.constants.RouteOption
import ai.pleos.playground.navi.data.ApplicationVisibleInfo
import ai.pleos.playground.navi.data.BookmarkInfo
import ai.pleos.playground.navi.data.CameraAlert
import ai.pleos.playground.navi.data.CurrentLocationInfo
import ai.pleos.playground.navi.data.DestinationArrivedInfo
import ai.pleos.playground.navi.data.DestinationInfo
import ai.pleos.playground.navi.data.DrivingInfo
import ai.pleos.playground.navi.data.FindRouteResult
import ai.pleos.playground.navi.data.RecentDestinationInfo
import ai.pleos.playground.navi.data.RouteInfo
import ai.pleos.playground.navi.data.RouteStartInfo
import ai.pleos.playground.navi.data.RouteStateInfo
import ai.pleos.playground.navi.data.TBTInfo
import ai.pleos.playground.navi.data.WaypointArrivedInfo
import ai.pleos.playground.navi.data.WaypointChangedInfo
import ai.pleos.playground.navi.data.WaypointInfo
import ai.pleos.playground.navi.helper.NaviHelper as PleosNaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.content.Context
import android.util.Log

object NaviHelper {

    private const val TAG = "NaviHelper"

    private var navi: PleosNaviHelper? = null
    private var isInitialized = false
    private var isPanelControlActive = false

    var onNavigationStarted: ((lotName: String, lat: Double, lng: Double) -> Unit)? = null
    var onNavigationEnded: (() -> Unit)? = null

    // ── 패널 소유권 ───────────────────────────────────────────────────────────

    fun takePanelControl(context: Context) {
        if (isPanelControlActive) return
        try {
            if (navi == null) {
                navi = PleosNaviHelper(context.applicationContext)
            }
            navi?.initialize()
            isPanelControlActive = true
            Log.d(TAG, "Panel control taken")
        } catch (e: Exception) {
            Log.w(TAG, "takePanelControl failed: ${e.message}")
        }
    }

    fun reacquirePanelControl(context: Context) {
        isPanelControlActive = false
        takePanelControl(context)
    }

    fun releasePanelControl() {
        // release()에서 일괄 처리
    }

    // ── SDK 초기화 ────────────────────────────────────────────────────────────

    fun init(context: Context) {
        if (isInitialized) { Log.d(TAG, "init: already initialized"); return }
        try {
            if (navi == null) {
                Log.d(TAG, "init: creating PleosNaviHelper instance")
                navi = PleosNaviHelper(context.applicationContext)
                Log.d(TAG, "init: calling initialize()")
                navi?.initialize()
                isPanelControlActive = true
                Log.d(TAG, "init: initialize() returned")
            }
            Log.d(TAG, "init: adding listener")
            navi?.addListener(routeListener)
            isInitialized = true
            Log.d(TAG, "NaviHelper initialized (navi=$navi)")
        } catch (e: Exception) {
            Log.w(TAG, "NaviHelper init failed: ${e.javaClass.simpleName}: ${e.message}")
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
        val n = navi
        if (n == null) {
            Log.w(TAG, "setDestination: navi is null — NaviHelper was not initialized successfully")
            return false
        }
        return try {
            // RouteInfo 생성자 순서: longitude, latitude, poiName, poiId, address, poiSubId, routeOption
            val routeInfo = RouteInfo(
                longitude   = lng,
                latitude    = lat,
                poiName     = lotName,
                poiId       = lotId,
                address     = "",
                poiSubId    = "0",
                routeOption = RouteOption.RECOMMENDED
            )
            n.requestRoute(routeInfo)
            onNavigationStarted?.invoke(lotName, lat, lng)
            Log.d(TAG, "requestRoute: $lotName lat=$lat lng=$lng")
            true
        } catch (e: Exception) {
            Log.w(TAG, "requestRoute failed: ${e.message}")
            false
        }
    }

    fun cancelNavigation() {
        try {
            navi?.cancelRoute()
        } catch (e: Exception) {
            Log.w(TAG, "cancelRoute failed: ${e.message}")
        }
        onNavigationEnded?.invoke()
    }

    // ── 리소스 해제 ───────────────────────────────────────────────────────────

    fun release() {
        try {
            navi?.removeListener(routeListener)
            navi?.release()
        } catch (_: Exception) {}
        navi                 = null
        isInitialized        = false
        isPanelControlActive = false
        onNavigationStarted  = null
        onNavigationEnded    = null
    }

    // ── 이벤트 리스너 ─────────────────────────────────────────────────────────

    private val routeListener = object : NaviHelperEventListener {
        override fun onRouteStarted(info: RouteStartInfo) {
            Log.d(TAG, "onRouteStarted")
        }
        override fun onRouteEnded() {
            Log.d(TAG, "onRouteEnded")
            onNavigationEnded?.invoke()
        }
        override fun onRouteCancelled() {
            Log.d(TAG, "onRouteCancelled")
            onNavigationEnded?.invoke()
        }
        override fun onDestinationArrived(info: DestinationArrivedInfo) {
            Log.d(TAG, "onDestinationArrived")
            onNavigationEnded?.invoke()
        }
        override fun onError(code: NaviErrorCode) {
            Log.w(TAG, "NaviHelper error: $code")
        }

        override fun onReRouteEnded() {}
        override fun onRouteOptionChanged(routeOption: RouteOption) {}
        override fun onWaypointChanged(info: WaypointChangedInfo) {}
        override fun onWayPointArrived(info: WaypointArrivedInfo) {}
        override fun onBookMarkChanged() {}
        override fun onDestinationChanged() {}
        override fun onApplicationVisibilityChangeRequest(info: ApplicationVisibleInfo) {}
        override fun onCurrentLocationInfo(info: CurrentLocationInfo) {}
        override fun onRouteStateInfo(info: RouteStateInfo) {}
        override fun onDestinationInfo(info: DestinationInfo) {}
        override fun onWayPointInfo(list: List<WaypointInfo>) {}
        override fun onRecentDestinationInfo(list: List<RecentDestinationInfo>) {}
        override fun onBookmarkInfo(list: List<BookmarkInfo>) {}
        override fun onUserDefinedRoute(result: FindRouteResult) {}
        override fun onCurrentRoadSpeedLimit(limit: Int) {}
        override fun onCameraAlert(list: List<CameraAlert>) {}
        override fun onDrivingInfo(info: DrivingInfo) {}
        override fun onNavigationStatus(status: RouteDriving) {}
        override fun onTBTInfo(list: List<TBTInfo>) {}
        override fun onChargerOperatorInfo(list: List<ai.pleos.playground.navi.data.ChargerOperator>) {}
    }
}
