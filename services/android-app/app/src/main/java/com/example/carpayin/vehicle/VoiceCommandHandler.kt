package com.example.carpayin.vehicle

import android.location.Location
import android.util.Log

object VoiceCommandHandler {

    private const val TAG = "VoiceCommand"

    var onShowParkingSection: (() -> Unit)? = null
    var onNavigateTo: ((GeofenceManager.ParkingLot) -> Unit)? = null

    fun handle(text: String) {
        val normalized = text.replace(" ", "")
        Log.d(TAG, "음성 명령: \"$text\"")

        when {
            isParkingQuery(normalized)      -> handleParkingQuery()
            isNavigationCommand(normalized) -> handleNavigation()
            else -> TtsHelper.speak("죄송합니다, 다시 말씀해 주세요")
        }
    }

    private fun isParkingQuery(text: String): Boolean =
        (text.contains("주차장") || text.contains("주차")) &&
        (text.contains("어디") || text.contains("추천") || text.contains("가까운") ||
         text.contains("근처") || text.contains("알려"))

    private fun isNavigationCommand(text: String): Boolean =
        text.contains("길안내") || text.contains("안내해줘") || text.contains("안내해주세요") ||
        text.contains("길좀알려줘") || text.contains("경로시작") ||
        (text.contains("안내") && (text.contains("시작") || text.contains("해줘")))

    private fun handleParkingQuery() {
        val lots = GeofenceManager.cachedParkingLots
        if (lots.isEmpty()) {
            TtsHelper.speak("현재 제휴 주차장 정보를 불러오는 중입니다")
            return
        }

        onShowParkingSection?.invoke()

        val nearest = nearestLot(lots) ?: lots.first()
        val hasLocation = NaviHelper.currentLat != 0.0 && NaviHelper.currentLng != 0.0

        if (hasLocation) {
            val dist = distMeters(nearest)
            val distText = if (dist < 1000) "${dist.toInt()}미터" else "${"%.1f".format(dist / 1000)}킬로미터"
            TtsHelper.speak("가장 가까운 제휴 주차장은 ${nearest.name}, ${distText} 거리에 있습니다. 길안내해줘 라고 말하면 바로 시작됩니다")
        } else {
            TtsHelper.speak("가장 가까운 제휴 주차장은 ${nearest.name}입니다. 길안내해줘 라고 말하면 바로 시작됩니다")
        }
    }

    private fun handleNavigation() {
        val lots = GeofenceManager.cachedParkingLots
        if (lots.isEmpty()) {
            TtsHelper.speak("주차장 정보를 불러오는 중입니다")
            return
        }
        val target = nearestLot(lots) ?: lots.first()
        onNavigateTo?.invoke(target)
    }

    private fun nearestLot(lots: List<GeofenceManager.ParkingLot>): GeofenceManager.ParkingLot? {
        if (NaviHelper.currentLat == 0.0 && NaviHelper.currentLng == 0.0) return null
        return lots.minByOrNull { distMeters(it) }
    }

    private fun distMeters(lot: GeofenceManager.ParkingLot): Float {
        val results = FloatArray(1)
        Location.distanceBetween(NaviHelper.currentLat, NaviHelper.currentLng, lot.lat, lot.lng, results)
        return results[0]
    }
}
