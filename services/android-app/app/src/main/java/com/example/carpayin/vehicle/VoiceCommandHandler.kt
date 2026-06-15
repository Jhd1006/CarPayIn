package com.example.carpayin.vehicle

import android.location.Location
import android.util.Log
import com.example.carpayin.R
import org.json.JSONException
import org.json.JSONObject

object VoiceCommandHandler {

    private const val TAG = "VoiceCommand"

    var onShowParkingSection: (() -> Unit)? = null
    var onNavigateTo: ((GeofenceManager.ParkingLot) -> Unit)? = null
    var onThinking: ((Boolean) -> Unit)? = null

    private val history = mutableListOf<Pair<String, String>>()
    private var pendingNavLot: GeofenceManager.ParkingLot? = null

    // lot_id → show_parking MP3 / navigation MP3 매핑
    val showParkingAudio = mapOf(
        "LOT_GANGNAM_01"       to R.raw.tts_show_gangnam,
        "LOT_HONGDAE_01"       to R.raw.tts_show_hongdae,
        "LOT_YEONGDEUNGPO_01"  to R.raw.tts_show_yeongdeungpo
    )
    val navAudio = mapOf(
        "LOT_GANGNAM_01"       to R.raw.tts_nav_gangnam,
        "LOT_HONGDAE_01"       to R.raw.tts_nav_hongdae,
        "LOT_YEONGDEUNGPO_01"  to R.raw.tts_nav_yeongdeungpo
    )

    private val SYSTEM_PROMPT = """
당신은 CarPayIn 차량용 AI 주차 어시스턴트입니다. 운전 중인 사용자를 돕습니다.
답변은 반드시 아래 JSON 형식으로만 출력하세요 (코드블록이나 다른 텍스트 없이):
{"action":"<action>","lot_id":"<lot_id 또는 null>"}

action 종류:
- show_parking: 사용자가 근처 주차장을 물어봄 → 가장 가까운 주차장 lot_id 반환
- start_navigation: 사용자가 길안내 수락 (그래/응/길안내해줘 등)
- decline: 사용자가 취소 또는 필요 없다고 함
- other: 주차/내비 외 대화

주차장 목록과 사용자 발화는 각 메시지에 포함됩니다.
    """.trimIndent()

    fun handle(userText: String) {
        Log.d(TAG, "음성 입력: \"$userText\"")
        onThinking?.invoke(true)

        val lots = GeofenceManager.cachedParkingLots
        val parkingContext = buildParkingContext(lots)

        if (history.isEmpty()) {
            LlmManager.startChat(SYSTEM_PROMPT)
        }

        val message = "$parkingContext\n\n사용자: $userText"

        LlmManager.send(
            text = message,
            onComplete = { responseText ->
                onThinking?.invoke(false)
                handleLlmResponse(userText, responseText, lots)
            },
            onError = {
                onThinking?.invoke(false)
                TtsHelper.playRaw(R.raw.tts_error)
            }
        )
    }

    private fun handleLlmResponse(
        userText: String,
        responseText: String,
        lots: List<GeofenceManager.ParkingLot>
    ) {
        val json = parseJson(responseText) ?: run {
            Log.w(TAG, "JSON 파싱 실패: $responseText")
            TtsHelper.playRaw(R.raw.tts_error)
            return
        }

        val action = json.optString("action", "other")
        val lotId  = json.optString("lot_id").takeIf { it.isNotBlank() && it != "null" }

        history.add("user" to userText)

        when (action) {
            "show_parking" -> {
                val lot = lotId?.let { id -> lots.find { it.id == id } } ?: nearestLot(lots)
                pendingNavLot = lot
                onShowParkingSection?.invoke()
                val resId = lot?.let { showParkingAudio[it.id] } ?: R.raw.tts_error
                TtsHelper.playRaw(resId)
            }
            "start_navigation" -> {
                val target = lotId?.let { id -> lots.find { it.id == id } }
                    ?: pendingNavLot ?: nearestLot(lots)
                if (target != null) {
                    val resId = navAudio[target.id] ?: R.raw.tts_error
                    TtsHelper.playRaw(resId) {
                        onShowParkingSection?.invoke()
                        onNavigateTo?.invoke(target)
                    }
                    pendingNavLot = null
                }
            }
            "decline" -> {
                TtsHelper.playRaw(R.raw.tts_decline)
                pendingNavLot = null
            }
            else -> {
                // other: TTS 폴백
                val msg = json.optString("message", "")
                if (msg.isNotBlank()) TtsHelper.speak(msg)
            }
        }
    }

    fun clearHistory() {
        history.clear()
        pendingNavLot = null
    }

    private fun buildParkingContext(lots: List<GeofenceManager.ParkingLot>): String {
        if (lots.isEmpty()) return "[현재 제휴 주차장 정보 없음]"
        val hasLocation = NaviHelper.currentLat != 0.0 && NaviHelper.currentLng != 0.0
        val sorted = if (hasLocation) lots.sortedBy { distMeters(it) } else lots
        val lines = sorted.mapIndexed { i, lot ->
            val distInfo = if (hasLocation) {
                val m = distMeters(lot)
                val distStr = if (m < 1000) "${m.toInt()}m" else "${"%.1f".format(m / 1000)}km"
                val minStr = "${(m / 500).toInt().coerceAtLeast(1)}분"
                " ($distStr, 약 $minStr)"
            } else ""
            "${i + 1}. ${lot.name} [${lot.id}]$distInfo"
        }
        return "[제휴 주차장 목록]\n${lines.joinToString("\n")}"
    }

    private fun parseJson(text: String): JSONObject? {
        val cleaned = text.trim()
            .removePrefix("```json").removePrefix("```")
            .removeSuffix("```").trim()
        return try {
            JSONObject(cleaned)
        } catch (_: JSONException) {
            val start = cleaned.indexOf('{')
            val end   = cleaned.lastIndexOf('}')
            if (start >= 0 && end > start) {
                runCatching { JSONObject(cleaned.substring(start, end + 1)) }.getOrNull()
            } else null
        }
    }

    private fun nearestLot(lots: List<GeofenceManager.ParkingLot>): GeofenceManager.ParkingLot? {
        if (lots.isEmpty()) return null
        if (NaviHelper.currentLat == 0.0 && NaviHelper.currentLng == 0.0) return lots.first()
        return lots.minByOrNull { distMeters(it) }
    }

    private fun distMeters(lot: GeofenceManager.ParkingLot): Float {
        val r = FloatArray(1)
        Location.distanceBetween(NaviHelper.currentLat, NaviHelper.currentLng, lot.lat, lot.lng, r)
        return r[0]
    }
}
