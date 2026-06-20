#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
from pyndn import Name, Face, Data
from pyndn.security import KeyChain


# Threshold (seconds) - how long the last MQTT data is still considered valid.
# Kept in sync with the FreshnessPeriod used in create_data_packet() so the
# Content Caching test behaves consistently.
DATA_STALE_THRESHOLD = 5


class SensorData:
    def __init__(self):
        self.temperature = 0.0
        self.humidity = 0.0
        self.timestamp = 0
        self.device = ""
        self.last_seen = 0.0  # waktu wall-clock saat terakhir terima data MQTT


class NDNGateway:
    def __init__(self, mqtt_broker, mqtt_port, mqtt_topic, ndn_prefix):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        self.ndn_prefix = ndn_prefix

        self.sensor_data = SensorData()
        self.data_lock = threading.Lock()

        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        self.face = Face()
        self.keychain = KeyChain()

        print("Gateway initialized")
        print(f"MQTT: {mqtt_broker}:{mqtt_port} topic={mqtt_topic}")
        print(f"NDN: {ndn_prefix}")

    def on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("MQTT connected")
            client.subscribe(self.mqtt_topic)
            print(f"MQTT subscribed to {self.mqtt_topic}")
        else:
            print(f"MQTT connection failed: {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)

            temp = data.get('temperature', data.get('suhu', 0.0))
            humid = data.get('humidity', data.get('kelembaban', 0.0))

            with self.data_lock:
                self.sensor_data.temperature = temp
                self.sensor_data.humidity = humid
                self.sensor_data.timestamp = data.get('timestamp', 0)
                self.sensor_data.device = data.get('device', 'unknown')
                self.sensor_data.last_seen = time.time()

            print(f"MQTT received: temp={temp} humid={humid}")

        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def register_prefix(self):
        try:
            prefix = Name(self.ndn_prefix)
            self.face.setCommandSigningInfo(self.keychain, self.keychain.getDefaultCertificateName())
            self.face.registerPrefix(prefix, self.on_interest, self.on_register_failed)
            print(f"NDN prefix registered: {self.ndn_prefix}")
        except Exception as e:
            print(f"NDN register error: {e}")

    def on_register_failed(self, prefix):
        print(f"NDN register failed: {prefix.toUri()}")

    def on_interest(self, prefix, interest, face, interestFilterId, filter):
        interest_name = interest.getName()
        name_str = interest_name.toUri()

        # Check data age before responding. If the last MQTT data is older
        # than DATA_STALE_THRESHOLD seconds (ESP32 is likely offline),
        # don't respond at all -> the Interest will time out on the
        # Consumer side, instead of the gateway endlessly sending stale data.
        with self.data_lock:
            age = time.time() - self.sensor_data.last_seen

        if self.sensor_data.last_seen == 0 or age > DATA_STALE_THRESHOLD:
            print(f"NDN request ignored, data is stale ({age:.1f}s) - ESP32 likely offline")
            return

        value = None
        data_type = None

        if "temperature" in name_str or "suhu" in name_str:
            with self.data_lock:
                value = self.sensor_data.temperature
            data_type = "temperature"
        elif "humidity" in name_str or "kelembaban" in name_str:
            with self.data_lock:
                value = self.sensor_data.humidity
            data_type = "humidity"
        else:
            print(f"NDN unknown request: {name_str}")
            return

        data_packet = self.create_data_packet(interest_name, value, data_type)

        if data_packet:
            face.putData(data_packet)
            print(f"NDN response: {data_type}={value}")
        else:
            print("NDN failed to create packet")

    def create_data_packet(self, name, value, data_type):
        try:
            data = Data(name)

            content = {
                "type": data_type,
                "value": value,
                "timestamp": int(time.time()),
                "device": self.sensor_data.device
            }

            content_str = json.dumps(content)
            data.setContent(content_str.encode('utf-8'))
            data.getMetaInfo().setFreshnessPeriod(10000)
            self.keychain.sign(data)

            return data
        except Exception as e:
            print(f"Error creating packet: {e}")
            return None

    def start_mqtt(self):
        try:
            print(f"MQTT connecting to {self.mqtt_broker}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"MQTT error: {e}")
            raise

    def start_ndn(self):
        print("NDN event loop started")
        try:
            while True:
                self.face.processEvents()
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("NDN loop stopped")
        except Exception as e:
            print(f"NDN error: {e}")

    def start(self):
        print("Gateway starting...")
        self.start_mqtt()
        time.sleep(2)
        self.register_prefix()

        ndn_thread = threading.Thread(target=self.start_ndn, daemon=True)
        ndn_thread.start()

        print("Gateway running (press Ctrl+C to stop)")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nGateway stopping...")
            self.stop()

    def stop(self):
        print("Stopping MQTT...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("Stopping NDN...")
        self.face.shutdown()
        print("Gateway stopped")


def main():
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    MQTT_TOPIC = "sensor/room1/data"
    NDN_PREFIX = "/sensor/room1"

    gateway = NDNGateway(MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, NDN_PREFIX)
    gateway.start()


if __name__ == "__main__":
    main()
