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
        ParkingLot("LOT_GANGNAM_01",   "강남주차장",  37.4979, 127.0276),
        ParkingLot("LOT_HONGDAE_01",   "홍대주차장",  37.5567, 126.9236),
        ParkingLot("LOT_YEONGDEUNGPO_01", "영등포주차장", 37.5258, 126.8962)
    )

    var onParkingLotsUpdated: ((List<ParkingLot>) -> Unit)? = null

    fun updateParkingLots(lots: List<ParkingLot>) {
        cachedParkingLots = lots
        Log.d(TAG, "주차장 목록 업데이트: ${lots.size}개")
        onParkingLotsUpdated?.invoke(lots)
    }
}
