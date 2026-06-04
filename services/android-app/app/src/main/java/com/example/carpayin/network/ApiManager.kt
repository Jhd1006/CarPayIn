package com.example.carpayin.network

import android.content.Context
import android.util.Log
import com.example.carpayin.config.AppConfig
import com.example.carpayin.data.ParkingStateManager
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class SessionExpiredException : Exception("세션이 만료되었습니다. 다시 로그인해 주세요.")

object ApiManager {
    private const val TAG = "ApiManager"
    val BASE_URL: String get() = AppConfig.backendBaseUrl
    val QR_BASE_URL: String get() = AppConfig.qrBaseUrl

    data class VehicleInfo(val carId: String, val modelName: String, val year: Int, val plateNumber: String = "")
    data class CardOrderResult(val orderId: String, val pgUrl: String)
    data class ParkingLotInfo(val id: String, val name: String, val lat: Double, val lng: Double)
    data class FeeResult(val lotName: String, val durationMinutes: Int, val amount: Int, val currency: String = "KRW")
    data class PaymentResult(val transactionId: String, val approvalNumber: String)
    data class TokenResult(val accessToken: String, val refreshToken: String)
    data class ConfirmCarResult(
        val accessToken: String,
        val refreshToken: String,
        val userId: String,
        val userName: String,
        val carId: String,
        val modelName: String,
        val plateNumber: String
    )

    fun <T> withAutoRefresh(context: Context, block: (token: String) -> T): T {
        val token = ParkingStateManager.getAccessToken(context) ?: throw SessionExpiredException()
        return try {
            block(token)
        } catch (e: RuntimeException) {
            if (!e.message.orEmpty().contains("401")) throw e
            val refreshToken = ParkingStateManager.getRefreshToken(context) ?: throw SessionExpiredException()
            try {
                val newTokens = refreshToken(refreshToken)
                ParkingStateManager.saveTokens(context, newTokens.accessToken, newTokens.refreshToken)
                block(newTokens.accessToken)
            } catch (re: RuntimeException) {
                ParkingStateManager.clearSession(context)
                throw SessionExpiredException()
            }
        }
    }

    data class SessionStatusResult(
        val isComplete: Boolean,
        val status: String = "pending",
        val accessToken: String = "",
        val refreshToken: String = "",
        val plateNumber: String = "",
        val userId: String = "",
        val userName: String = "",
        val modelName: String = "",
        val vehicleList: List<VehicleInfo> = emptyList(),
        val cardLastFour: String = "****",
        val cardBrand: String = "현대카드",
        val debugMessage: String = ""
    )

    fun checkLoginSession(sessionId: String): SessionStatusResult {
        val bases = linkedSetOf(BASE_URL, QR_BASE_URL).map { it.trimEnd('/') }
        val messages = mutableListOf<String>()

        for (baseUrl in bases) {
            try {
                val response = getJson(URL("$baseUrl/auth/session/$sessionId/status"))
                val status = response.optString("status", "pending")
                val serverMessage = response.optString("debug_message", "")
                val message = if (serverMessage.isNotBlank()) {
                    "$baseUrl -> $status: $serverMessage"
                } else {
                    "$baseUrl -> $status"
                }
                messages.add(message)
                Log.d(TAG, "login session ${sessionId.take(8)} $message")

                if (status == "complete") {
                    return parseCompleteSession(response).copy(debugMessage = message)
                }
                if (status != "pending") {
                    return SessionStatusResult(
                        isComplete = false,
                        status = status,
                        debugMessage = message
                    )
                }
            } catch (e: Exception) {
                val message = "$baseUrl -> ${e.message}"
                messages.add(message)
                Log.w(TAG, "login session ${sessionId.take(8)} $message")
            }
        }

        return SessionStatusResult(
            isComplete = false,
            status = "pending",
            debugMessage = messages.joinToString(" / ")
        )
    }

    fun createQrSession(loginSessionId: String, vinHash: String): String {
        val body = JSONObject().apply {
            put("login_session_id", loginSessionId)
            put("vin_hash", vinHash)
        }.toString()
        val response = postJson(URL("$BASE_URL/auth/qr-session"), body)
        return response.optString("login_url", "")
    }

    private fun parseCompleteSession(response: JSONObject): SessionStatusResult {
        val vehicleArray = response.optJSONArray("cars")
            ?: response.optJSONArray("vehicles")
            ?: response.optJSONArray("vin_list")
        val vehicleList = mutableListOf<VehicleInfo>()
        if (vehicleArray != null) {
            for (i in 0 until vehicleArray.length()) {
                val item = vehicleArray.getJSONObject(i)
                vehicleList.add(VehicleInfo(
                    carId     = item.optString("car_id", ""),
                    modelName = item.optString("model_name", item.optString("car_sellname", "")),
                    year      = item.optInt("year", 0),
                    plateNumber = item.optString("plate", item.optString("plate_number", ""))
                ))
            }
        }
        val firstVehicle = vehicleList.firstOrNull()

        return SessionStatusResult(
            isComplete   = true,
            status       = "complete",
            accessToken  = response.optString("temp_access_token", response.optString("access_token", "")),
            refreshToken = response.optString("refresh_token", ""),
            plateNumber  = response.optString("plate_number", firstVehicle?.plateNumber.orEmpty()),
            userId       = response.optString("user_id", ""),
            userName     = response.optString("name", response.optString("user_name", "")),
            modelName    = response.optString("model_name", firstVehicle?.modelName.orEmpty()),
            vehicleList  = vehicleList,
            cardLastFour = response.optString("card_last_four", "****"),
            cardBrand    = response.optString("card_brand", "현대카드")
        )
    }

    fun confirmCar(vinHash: String, carId: String, accessToken: String): ConfirmCarResult {
        val body = JSONObject().apply {
            put("vin_hash", vinHash)
            put("car_id", carId)
        }.toString()
        val response = postJson(URL("$BASE_URL/auth/confirm-car"), body, accessToken)
        val car = response.optJSONObject("car")
        return ConfirmCarResult(
            accessToken = response.getString("app_access_token"),
            refreshToken = response.getString("app_refresh_token"),
            userId = response.optString("user_id", ""),
            userName = response.optString("name", ""),
            carId = response.optString("car_id", carId),
            modelName = car?.optString("model_name", car.optString("car_sellname", "")) ?: "",
            plateNumber = car?.optString("plate", car.optString("plate_number", "")) ?: ""
        )
    }

    fun refreshToken(refreshToken: String): TokenResult {
        val body = JSONObject().apply { put("refresh_token", refreshToken) }.toString()
        val response = postJson(URL("$BASE_URL/auth/refresh"), body)
        return TokenResult(
            response.optString("app_access_token", response.optString("access_token", "")),
            response.optString("app_refresh_token", response.optString("refresh_token", refreshToken))
        )
    }

    fun unregister(accessToken: String) {
        postJson(URL("$BASE_URL/auth/unregister"), "{}", accessToken)
    }

    fun createCardOrder(plate: String, bankName: String, agreeTerms: Boolean, accessToken: String): CardOrderResult {
        val body = JSONObject().apply {
            put("plate", plate)
            put("bank_name", bankName)
            put("agree_terms", agreeTerms)
        }.toString()
        val response = postJson(URL("$BASE_URL/card/order"), body, accessToken)
        return CardOrderResult(response.getString("order_id"), response.getString("pg_url"))
    }

    fun fetchCardOrderLegacy(accessToken: String): CardOrderResult {
        val response = getJson(URL("$BASE_URL/card/order"), accessToken)
        return CardOrderResult(response.getString("order_id"), response.getString("pg_url"))
    }

    fun fetchParkingLots(): List<ParkingLotInfo> {
        return try {
            val response = getJson(URL("$BASE_URL/parking/lots"))
            val arr = response.optJSONArray("lots") ?: return emptyList()
            (0 until arr.length()).map { i ->
                val item = arr.getJSONObject(i)
                ParkingLotInfo(item.getString("id"), item.getString("name"), item.getDouble("lat"), item.getDouble("lng"))
            }
        } catch (e: Exception) {
            listOf(
                ParkingLotInfo("LOT_TEST_01", "테스트 주차장", 37.493087, 127.049750),
                ParkingLotInfo("LOT_GN_01", "강남 CarPayIn 주차장", 37.4979, 127.0276),
                ParkingLotInfo("LOT_HD_01", "홍대 CarPayIn 주차장", 37.5567, 126.9236)
            )
        }
    }

    fun sendPreNotification(carId: String, plate: String, lotId: String, triggerType: String, accessToken: String) {
        val body = JSONObject().apply {
            put("car_id", carId); put("plate", plate); put("lot_id", lotId); put("trigger", triggerType.lowercase())
        }.toString()
        postJson(URL("$BASE_URL/pre-notify"), body, accessToken)
    }

    fun queryFee(fallbackLotId: String, sessionId: String, accessToken: String): FeeResult {
        val response = getJson(URL("$BASE_URL/fee/$sessionId"), accessToken)
        val duration = if (response.has("duration_minutes")) {
            response.optInt("duration_minutes", 0)
        } else {
            response.optInt("duration", 0)
        }
        return FeeResult(
            response.optString("lot_name", response.optString("lot_id", fallbackLotId)),
            duration,
            response.getInt("amount"),
            response.optString("currency", "KRW")
        )
    }

    fun requestPayment(sessionId: String, amount: Int, accessToken: String, currency: String = "KRW"): PaymentResult {
        val body = JSONObject().apply {
            put("session_id", sessionId)
            put("amount", amount)
            put("currency", currency)
        }.toString()
        val response = postJson(URL("$BASE_URL/payment"), body, accessToken)
        return PaymentResult(response.getString("tx_id"), response.getString("approval_no"))
    }

    private fun postJson(url: URL, body: String, accessToken: String? = null): JSONObject {
        val conn = url.openConnection() as HttpURLConnection
        return try {
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("ngrok-skip-browser-warning", "true")
            if (accessToken != null) conn.setRequestProperty("Authorization", "Bearer $accessToken")
            conn.doOutput = true
            conn.connectTimeout = 10_000
            conn.readTimeout = 30_000
            OutputStreamWriter(conn.outputStream).use { it.write(body) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.readText() ?: "{}"
            if (code !in 200..299) throw RuntimeException("HTTP $code: $text")
            JSONObject(text)
        } finally { conn.disconnect() }
    }

    private fun getJson(url: URL, accessToken: String? = null): JSONObject {
        val conn = url.openConnection() as HttpURLConnection
        return try {
            conn.requestMethod = "GET"
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("ngrok-skip-browser-warning", "true")
            if (accessToken != null) conn.setRequestProperty("Authorization", "Bearer $accessToken")
            conn.connectTimeout = 10_000
            conn.readTimeout = 30_000
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.readText() ?: "{}"
            if (code !in 200..299) throw RuntimeException("HTTP $code: $text")
            JSONObject(text)
        } finally { conn.disconnect() }
    }
}
