package com.example.carpayin.network

import android.content.Context
import android.util.Log
import com.amazonaws.auth.CognitoCachingCredentialsProvider
import com.amazonaws.mobileconnectors.iot.AWSIotMqttClientStatusCallback.AWSIotMqttClientStatus
import com.amazonaws.mobileconnectors.iot.AWSIotMqttManager
import com.amazonaws.mobileconnectors.iot.AWSIotMqttQos
import com.amazonaws.regions.Regions
import org.json.JSONObject

object MqttManager {
    private const val TAG = "MqttManager"
    private const val IDENTITY_POOL_ID = "ap-northeast-2:bd67c4db-bbb7-4768-9ca9-552f1e0d4d12"
    private const val IOT_ENDPOINT = "a2etz9h9ig30tw-ats.iot.ap-northeast-2.amazonaws.com"

    private var mqttManager: AWSIotMqttManager? = null
    private var connected = false

    var onParkingConfirmed: ((lotId: String, sessionId: String) -> Unit)? = null
    var onPaymentComplete: ((transactionId: String, approvalNumber: String, lotId: String, amount: Int) -> Unit)? = null
    var onConnectionLost: ((cause: Throwable?) -> Unit)? = null

    fun connect(context: Context, carId: String) {
        try {
            val credentialsProvider = CognitoCachingCredentialsProvider(
                context,
                IDENTITY_POOL_ID,
                Regions.AP_NORTHEAST_2
            )

            val clientId = "carpayin-${carId.takeLast(8)}-${System.currentTimeMillis()}"
            mqttManager = AWSIotMqttManager(clientId, IOT_ENDPOINT).apply {
                keepAlive = 60
            }

            mqttManager!!.connect(credentialsProvider) { status, throwable ->
                when (status) {
                    AWSIotMqttClientStatus.Connected -> {
                        Log.d(TAG, "IoT Core 연결 성공")
                        connected = true
                        subscribeTopics(carId)
                    }
                    AWSIotMqttClientStatus.ConnectionLost -> {
                        Log.w(TAG, "IoT Core 연결 끊김")
                        connected = false
                        onConnectionLost?.invoke(throwable)
                    }
                    else -> Log.d(TAG, "IoT Core 상태: $status")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "IoT Core 연결 실패: ${e.message}")
        }
    }

    private fun subscribeTopics(carId: String) {
        mqttManager?.subscribeToTopic("parking/confirmed/$carId", AWSIotMqttQos.QOS1) { _, data ->
            runCatching {
                val payload = JSONObject(String(data))
                val lotId     = payload.optString("lot_id", "")
                val sessionId = payload.optString("session_id", "")
                Log.d(TAG, "입차 확정 수신: lot=$lotId")
                onParkingConfirmed?.invoke(lotId, sessionId)
            }.onFailure { Log.e(TAG, "입차 확정 파싱 오류: ${it.message}") }
        }

        mqttManager?.subscribeToTopic("payment/complete/$carId", AWSIotMqttQos.QOS1) { _, data ->
            runCatching {
                val payload    = JSONObject(String(data))
                val txId       = payload.optString("transaction_id", "")
                val approvalNo = payload.optString("approval_number", "")
                val lotId      = payload.optString("lot_id", "")
                val amount     = payload.optInt("amount", 0)
                Log.d(TAG, "결제 완료 수신: tx=$txId, amount=$amount")
                onPaymentComplete?.invoke(txId, approvalNo, lotId, amount)
            }.onFailure { Log.e(TAG, "결제 완료 파싱 오류: ${it.message}") }
        }
    }

    fun isConnected(): Boolean = connected

    fun disconnect() {
        try {
            mqttManager?.disconnect()
            connected = false
            Log.d(TAG, "IoT Core 연결 해제")
        } catch (e: Exception) {
            Log.w(TAG, "IoT Core 해제 오류: ${e.message}")
        } finally {
            mqttManager = null
        }
    }
}
