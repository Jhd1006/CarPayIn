package com.example.carpayin.vehicle

import android.util.Log

object GeofenceManager {
    private const val TAG = "GeofenceManager"

    data class ParkingLot(
        val id: String,
        val name: String,
        val lat: Double,
        val lng: Double
    )

    var cachedParkingLots: List<ParkingLot> = listOf(
        ParkingLot("LOT_TEST_01",         "42dot 테스트 주차장", 37.48544722, 127.03636666),
        ParkingLot("LOT_GANGNAM_01",      "강남 아이파킹",    37.4979,   127.0276),
        ParkingLot("LOT_SEOCHO_01",       "서초 아이파킹",    37.4837,   127.0324),
        ParkingLot("LOT_YEONGDEUNGPO_01", "영등포 아이파킹",  37.5258,   126.8962)
    )

    var onParkingLotsUpdated: ((List<ParkingLot>) -> Unit)? = null

    fun updateParkingLots(lots: List<ParkingLot>) {
        cachedParkingLots = lots
        Log.d(TAG, "주차장 목록 업데이트: ${lots.size}개")
        onParkingLotsUpdated?.invoke(lots)
    }
}
