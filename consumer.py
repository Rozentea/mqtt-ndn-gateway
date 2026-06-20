#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pyndn import Name, Face, Interest
import time
import json
from datetime import datetime


class SensorConsumer:
    def __init__(self, prefix):
        self.prefix = prefix
        self.face = Face()
        self.temp_done = False
        self.humid_done = False
        print("Consumer initialized")
        print(f"NDN prefix: {prefix}")

    def on_data_temperature(self, interest, data):
        self.temp_done = True
        try:
            content = data.getContent().toBytes().decode('utf-8')
            data_json = json.loads(content)
            temp = data_json.get('value', 'N/A')
            device = data_json.get('device', 'unknown')
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Temperature: {temp} C (from {device})")
        except Exception as e:
            print(f"Error: {e}")

    def on_timeout_temperature(self, interest):
        self.temp_done = True
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Timeout: temperature request")

    def on_data_humidity(self, interest, data):
        self.humid_done = True
        try:
            content = data.getContent().toBytes().decode('utf-8')
            data_json = json.loads(content)
            humid = data_json.get('value', 'N/A')
            device = data_json.get('device', 'unknown')
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Humidity: {humid} % (from {device})")
        except Exception as e:
            print(f"Error: {e}")

    def on_timeout_humidity(self, interest):
        self.humid_done = True
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Timeout: humidity request")

    def request_temperature(self):
        name = Name(f"{self.prefix}/temperature")
        interest = Interest(name)
        interest.setMustBeFresh(True)
        interest.setInterestLifetimeMilliseconds(4000)
        self.face.expressInterest(interest, self.on_data_temperature, self.on_timeout_temperature)

    def request_humidity(self):
        name = Name(f"{self.prefix}/humidity")
        interest = Interest(name)
        interest.setMustBeFresh(True)
        interest.setInterestLifetimeMilliseconds(4000)
        self.face.expressInterest(interest, self.on_data_humidity, self.on_timeout_humidity)

    def request_both(self):
        self.temp_done = False
        self.humid_done = False

        self.request_temperature()
        self.request_humidity()

        # Stop polling once BOTH responses (data or timeout) have been received,
        # instead of always waiting a full 5 seconds. The max_wait safety margin
        # is slightly above the Interest lifetime (4 seconds) in case the
        # callback is not triggered.
        max_wait = 4.5
        start = time.time()
        while not (self.temp_done and self.humid_done):
            self.face.processEvents()
            time.sleep(0.01)
            if time.time() - start > max_wait:
                break

    def run_continuous(self, interval=1):
        print(f"Starting continuous mode (interval: {interval}s)")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                self.request_both()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nConsumer stopped")


def main():
    NDN_PREFIX = "/sensor/room1"
    INTERVAL = 1  # seconds between request cycles (previously 3, now faster)

    consumer = SensorConsumer(NDN_PREFIX)
    consumer.run_continuous(interval=INTERVAL)


if __name__ == "__main__":
    main()
