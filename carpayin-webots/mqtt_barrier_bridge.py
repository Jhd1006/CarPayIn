#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CarPayIn MQTT 차단기 브리지
carpayin/barrier 토픽 수신 → barrier_controller HTTP REST 호출
"""
import json, urllib.request, paho.mqtt.client as mqtt, os

MQTT_HOST          = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT          = int(os.getenv("MQTT_PORT", "1883"))
BARRIER_ENTRY_URL  = os.getenv("BARRIER_ENTRY_URL", "http://localhost:8100/open")
BARRIER_EXIT_URL   = os.getenv("BARRIER_EXIT_URL",  "http://localhost:8101/open")

def post(url):
    try:
        req = urllib.request.Request(
            url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            print(f"[BRIDGE] {url} -> {r.status} {r.read().decode()}", flush=True)
    except Exception as e:
        print(f"[BRIDGE] 실패 {url}: {e}", flush=True)

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[BRIDGE] MQTT 연결 rc={rc}", flush=True)
    client.subscribe("carpayin/barrier")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        gate   = payload.get("gate", "")
        action = payload.get("action", "")
        print(f"[BRIDGE] {msg.topic}: gate={gate} action={action}", flush=True)
        if action == "open":
            if gate == "entry":
                post(BARRIER_ENTRY_URL)
            elif gate == "exit":
                post(BARRIER_EXIT_URL)
    except Exception as e:
        print(f"[BRIDGE] 파싱 오류: {e}", flush=True)

mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mq.on_connect = on_connect
mq.on_message = on_message

print(f"[BRIDGE] {MQTT_HOST}:{MQTT_PORT} 연결 중...", flush=True)
while True:
    try:
        mq.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mq.loop_forever()
    except Exception as e:
        print(f"[BRIDGE] 재연결 시도: {e}", flush=True)
        import time; time.sleep(5)
