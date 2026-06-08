package com.example.carpayin.vehicle

import android.content.Context
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.util.Log
import com.example.carpayin.BuildConfig
import com.example.carpayin.config.AppConfig

/**
 * 동적 지오펜스 매니저 (BleManager 대체)
 *
 * ▸ VHAL 차량 속도에 따라 지오펜스 반경을 동적으로 조정합니다.
 *     · 30km/h 미만  → 300m
 *     · 30~60km/h   → 600m
 *     · 60km/h 초과  → 1km
 *   네트워크 지연이 있어도 차량이 차단기 도착 전에 사전 알림이 완료되도록 보장.
 *
 * ▸ 제휴 주차장 목록은 앱 초기화 시 백엔드에서 수신해 로컬 캐싱합니다.
 *   (현재는 Mock 데이터 사용)
 *
 * ▸ NaviHelper SDK 목적지 변경 콜백 연동 포인트를 제공합니다.
 *   실제 SDK 연동 시 onNaviDestinationChanged()를 NaviHelper 리스너에서 호출하세요.
 */
object GeofenceManager {
    private const val TAG = "GeofenceManager"

    // ── 제휴 주차장 데이터 ────────────────────────────────────────────────────

    data class ParkingLot(
        val id: String,
        val name: String,
        val lat: Double,
        val lng: Double
    )

    data class VehicleLocation(
        val lat: Double,
        val lng: Double,
        val speedKph: Float,
        val provider: String,
        val updatedAtMs: Long
    )

    /**
     * 앱 초기화 시 백엔드에서 내려받아 캐싱하는 제휴 주차장 목록.
     * TODO: ApiManager.fetchParkingLots() 연동 후 이 목록을 교체
     *
     * [Pleos 기본 내비 테스트 위치]
     *   42dot: lat=37.48544722, lng=127.03636666
     */
    var cachedParkingLots: List<ParkingLot> = listOf(
        // Pleos NaviHelper 공식 예제와 같은 42dot 위치
        ParkingLot("LOT_TEST_01",         "42dot 테스트 주차장", 37.48544722, 127.03636666),
        // Mock 데이터
        ParkingLot("LOT_GANGNAM_01",      "강남 아이파킹",    37.4979,   127.0276),
        ParkingLot("LOT_SEOCHO_01",       "서초 아이파킹",    37.4837,   127.0324),
        ParkingLot("LOT_YEONGDEUNGPO_01", "영등포 아이파킹",  37.5258,   126.8962)
    )

    /** 백엔드에서 수신한 주차장 목록으로 캐시 갱신 */
    fun updateParkingLots(lots: List<ParkingLot>) {
        cachedParkingLots = lots
        Log.d(TAG, "주차장 목록 업데이트: ${lots.size}개")
        onParkingLotsUpdated?.invoke(lots)
    }

    // ── 상태 ─────────────────────────────────────────────────────────────────

    private var locationManager: LocationManager? = null
    private val detectedLots = mutableSetOf<String>()  // 세션 내 중복 감지 방지
    @Volatile
    var lastVehicleLocation: VehicleLocation? = null
        private set

    /**
     * 콜백: 지오펜스 진입 or 내비 목적지 설정
     * @param lotId       주차장 ID
     * @param lotName     주차장 이름
     * @param triggerType "GEOFENCE" | "NAVI"
     */
    var onParkingLotApproach: ((lotId: String, lotName: String, triggerType: String) -> Unit)? = null
    var onVehicleLocationUpdated: ((VehicleLocation) -> Unit)? = null
    var onParkingLotsUpdated: ((List<ParkingLot>) -> Unit)? = null

    // ── 시작 / 중지 ───────────────────────────────────────────────────────────

    fun start(context: Context) {
        locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        try {
            locationManager?.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                5_000L,   // 최소 갱신 간격 5초
                10f,      // 최소 이동 거리 10m
                locationListener
            )
            Log.d(TAG, "위치 업데이트 시작 (GPS)")
        } catch (e: SecurityException) {
            Log.w(TAG, "위치 권한 없음 → 네트워크 Provider 시도: ${e.message}")
            try {
                locationManager?.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    10_000L, 50f,
                    locationListener
                )
            } catch (e2: SecurityException) {
                if (BuildConfig.DEBUG) {
                    Log.e(TAG, "네트워크 위치도 실패 — 디버그 시뮬레이션 모드: ${e2.message}")
                    startSimulated()
                } else {
                    Log.e(TAG, "네트워크 위치도 실패 — 릴리즈 빌드에서는 시뮬레이션 폴링 생략: ${e2.message}")
                }
            }
        }
    }

    // ── 위치 리스너 ───────────────────────────────────────────────────────────

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            // 차량 속도에 따라 반경 동적 결정
            val speedKph = location.speed * 3.6f
            updateVehicleLocation(location, speedKph)
            val radius = dynamicRadius(speedKph)
            checkGeofence(location, radius, speedKph)
        }

        @Deprecated("deprecated in API 29")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }

    // ── 동적 반경 계산 ────────────────────────────────────────────────────────

    /**
     * 속도가 빠를수록 반경을 넓혀 네트워크 지연에도 사전 등록이 미리 완료되도록 보장.
     */
    private fun dynamicRadius(speedKph: Float): Float = when {
        speedKph < 30f  -> 300f
        speedKph < 60f  -> 600f
        else            -> 1000f
    }

    // ── 지오펜스 체크 ─────────────────────────────────────────────────────────

    private fun checkGeofence(location: Location, radius: Float, speedKph: Float) {
        for (lot in cachedParkingLots) {
            if (lot.id in detectedLots) continue

            val lotLoc = Location("").apply {
                latitude  = lot.lat
                longitude = lot.lng
            }
            val dist = location.distanceTo(lotLoc)
            if (dist <= radius) {
                Log.d(TAG, "지오펜스 진입: ${lot.name} | 거리 ${dist.toInt()}m | 반경 ${radius.toInt()}m | 속도 ${"%.1f".format(speedKph)}km/h")
                detectedLots.add(lot.id)
                onParkingLotApproach?.invoke(lot.id, lot.name, "GEOFENCE")
            }
        }
    }

    private fun updateVehicleLocation(location: Location, speedKph: Float) {
        val current = VehicleLocation(
            lat = location.latitude,
            lng = location.longitude,
            speedKph = speedKph,
            provider = location.provider ?: "gps",
            updatedAtMs = System.currentTimeMillis()
        )
        lastVehicleLocation = current
        onVehicleLocationUpdated?.invoke(current)
    }

    // ── NaviHelper SDK 연동 포인트 ────────────────────────────────────────────

    /**
     * NaviHelper SDK의 목적지 변경 콜백에서 이 메서드를 호출하세요.
     * 목적지가 제휴 주차장이면 즉시 사전 알림 트리거.
     *
     * 예시:
     *   naviHelper.setOnDestinationChangedListener { name, lat, lng ->
     *       GeofenceManager.onNaviDestinationChanged(name, lat, lng)
     *   }
     */
    fun onNaviDestinationChanged(destinationName: String, lat: Double, lng: Double) {
        val destLoc = Location("").apply {
            latitude  = lat
            longitude = lng
        }
        for (lot in cachedParkingLots) {
            if (lot.id in detectedLots) continue
            val lotLoc = Location("").apply {
                latitude  = lot.lat
                longitude = lot.lng
            }
            if (destLoc.distanceTo(lotLoc) < 100f) {
                Log.d(TAG, "내비 목적지가 제휴 주차장: ${lot.name}")
                detectedLots.add(lot.id)
                onParkingLotApproach?.invoke(lot.id, lot.name, "NAVI")
                return
            }
        }
    }

    // ── 에뮬레이터 / 위치 미지원 시뮬레이션 ─────────────────────────────────

    private var simThread: Thread? = null
    private var simRunning = false

    private fun startSimulated() {
        Log.d(TAG, "시뮬레이션 모드: 백엔드 /sim/location 폴링 시작 (3초 간격)")
        simRunning = true
        simThread = Thread {
            while (simRunning) {
                try {
                    val url = java.net.URL("${AppConfig.backendBaseUrl}/sim/location")
                    val conn = url.openConnection() as java.net.HttpURLConnection
                    conn.connectTimeout = 3000
                    conn.readTimeout    = 3000
                    val body = conn.inputStream.bufferedReader().readText()
                    val json = org.json.JSONObject(body)
                    val lat  = json.getDouble("lat")
                    val lng  = json.getDouble("lng")

                    val loc = android.location.Location("sim").apply {
                        latitude  = lat
                        longitude = lng
                        speed     = (json.optDouble("speed_kph", 0.0) / 3.6).toFloat()
                    }
                    val speedKph = loc.speed * 3.6f
                    updateVehicleLocation(loc, speedKph)
                    checkGeofence(loc, dynamicRadius(speedKph), speedKph)
                    Log.d(TAG, "[시뮬레이션] lat=${"%.6f".format(lat)} lng=${"%.6f".format(lng)}")
                } catch (e: Exception) {
                    Log.w(TAG, "시뮬레이션 위치 조회 실패: ${e.message}")
                }
                Thread.sleep(3000)
            }
        }.also { it.isDaemon = true; it.start() }
    }

    fun clearDetectedLots() {
        detectedLots.clear()
        Log.d(TAG, "지오펜스 감지 캐시 초기화 (결제 완료 후 재방문 대비)")
    }

    fun stop() {
        simRunning = false
        simThread?.interrupt()
        simThread = null
        try { locationManager?.removeUpdates(locationListener) } catch (e: Exception) {}
        detectedLots.clear()
        Log.d(TAG, "위치 업데이트 중지, 감지 캐시 초기화")
    }

    fun isActive(): Boolean = locationManager != null || simRunning
}
