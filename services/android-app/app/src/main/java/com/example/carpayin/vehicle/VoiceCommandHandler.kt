package com.example.carpayin.vehicle

import android.location.Location
import android.util.Log
import org.json.JSONException
import org.json.JSONObject

object VoiceCommandHandler {

    private const val TAG = "VoiceCommand"

    // MainActivity 콜백
    var onShowParkingSection: (() -> Unit)? = null
    var onNavigateTo: ((GeofenceManager.ParkingLot) -> Unit)? = null
    var onThinking: ((Boolean) -> Unit)? = null  // LLM 처리 중 표시

    // 대화 기록 (멀티턴 맥락 유지)
    private val history = mutableListOf<Pair<String, String>>() // role to content
    private var pendingNavLot: GeofenceManager.ParkingLot? = null

    private val SYSTEM_PROMPT = """
당신은 CarPayIn 차량용 AI 주차 어시스턴트입니다. 운전 중인 사용자를 돕습니다.
답변은 반드시 아래 JSON 형식으로만 출력하세요 (코드블록이나 다른 텍스트 없이):
{"action":"<action>","message":"<30자 이내 한국어>","lot_id":"<lot_id 또는 null>"}

action 종류:
- show_parking: 가장 가까운 주차장 안내 후 길안내 여부 질문
- start_navigation: 사용자가 길안내 수락 → 길안내 시작
- decline: 사용자가 취소 또는 필요 없다고 함
- other: 주차/내비 외 대화

주차장 목록과 사용자 발화는 각 메시지에 포함됩니다.
응답 message는 TTS로 읽히므로 자연스러운 말투로 짧게 써주세요.
    """.trimIndent()

    fun handle(userText: String) {
        Log.d(TAG, "음성 입력: \"$userText\"")
        onThinking?.invoke(true)

        val lots = GeofenceManager.cachedParkingLots
        val parkingContext = buildParkingContext(lots)

        // 첫 발화면 세션 시작
        if (history.isEmpty()) {
            LlmManager.startChat(SYSTEM_PROMPT)
        }

        // 주차장 현황을 매 발화에 주입 (위치 변화 반영)
        val message = "$parkingContext\n\n사용자: $userText"

        LlmManager.send(
            text = message,
            onComplete = { responseText ->
                onThinking?.invoke(false)
                handleLlmResponse(userText, responseText, lots)
            },
            onError = {
                onThinking?.invoke(false)
                TtsHelper.speak("죄송합니다, 잠시 후 다시 말씀해 주세요")
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
            TtsHelper.speak("죄송합니다, 다시 말씀해 주세요")
            return
        }

        val action  = json.optString("action", "other")
        val message = json.optString("message", "")
        val lotId   = json.optString("lot_id").takeIf { it.isNotBlank() && it != "null" }

        // 세션 활성 여부 추적 (startChat 중복 방지용)
        history.add("user" to userText)

        // 메시지 음성 출력
        if (message.isNotBlank()) TtsHelper.speak(message)

        when (action) {
            "show_parking" -> {
                onShowParkingSection?.invoke()
                // 안내할 주차장 저장 (다음 "그래" 대응)
                pendingNavLot = lotId?.let { id -> lots.find { it.id == id } }
                    ?: nearestLot(lots)
            }
            "start_navigation" -> {
                val target = lotId?.let { id -> lots.find { it.id == id } }
                    ?: pendingNavLot
                    ?: nearestLot(lots)
                if (target != null) {
                    onShowParkingSection?.invoke()
                    onNavigateTo?.invoke(target)
                    pendingNavLot = null
                }
            }
            "decline" -> {
                pendingNavLot = null
            }
            else -> { /* other: TTS만 재생 */ }
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
        // LLM이 ```json ... ``` 블록으로 감쌀 경우 제거
        val cleaned = text.trim()
            .removePrefix("```json").removePrefix("```")
            .removeSuffix("```").trim()
        return try {
            JSONObject(cleaned)
        } catch (_: JSONException) {
            // JSON이 중간에 시작하는 경우 찾아서 파싱
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
