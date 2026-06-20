# Hybrid MQTT-NDN Gateway

A Python-based translation gateway that bridges a conventional IP-based IoT ecosystem (MQTT) into a Named Data Networking (NDN) environment. The project demonstrates how resource-constrained devices such as the ESP32 — which currently lack stable NDN payload support — can still participate in a content-centric network through a hybrid bridge.

## Overview

IoT communication today is dominated by host-centric, IP-based architectures, while Named Data Networking (NDN) offers a content-centric paradigm that is arguably more suitable for large-scale data distribution. However, native NDN libraries for low-cost microcontrollers like the ESP32 are still limited to basic connectivity (ping) without reliable payload transmission.

This project solves that gap with a **Hybrid MQTT-NDN Bridge**:

1. An ESP32 + DHT22 sensor publishes temperature/humidity readings over MQTT (a protocol stack that is mature and stable on constrained hardware).
2. A Python gateway subscribes to the MQTT broker, maps each reading into NDN's naming scheme, and serves it as a Data Packet in response to NDN Interests.
3. An NDN consumer requests data using Interest Packets, transparently benefiting from NDN features such as in-network caching (Content Store) on NFD.

## Architecture

```
┌─────────────┐     MQTT      ┌─────────────────┐     NDN      ┌──────────────┐
│   ESP32 +   │ ───Publish──► │  Mosquitto +     │ ◄──Interest──│   Consumer   │
│   DHT22     │               │  Python Gateway  │ ───Data────► │  (VM 2 / NFD)│
│ (Producer)  │               │  (VM 1 / NFD)    │              │              │
└─────────────┘               └──────────────────┘              └──────────────┘
```

- **VM 1 (Gateway Node):** runs Mosquitto broker, the Python translation gateway (`ndn_gateway_simple.py`), and NFD.
- **VM 2 (Consumer Node):** runs NFD and the NDN consumer application (`ndn_consumer_simple.py`).
- The two VMs are connected over a dedicated **Internal Network** segment, isolated from the IP/MQTT traffic, so NDN Interest/Data exchange can be captured and analyzed independently (e.g., with Wireshark).

## Features

- Real-time MQTT-to-NDN payload translation
- Hierarchical NDN naming scheme (`/sensor/room1/temperature`, `/sensor/room1/humidity`)
- Content Store (CS) caching support via NFD, with a configurable `FreshnessPeriod`
- Stale-data protection: the gateway stops responding to Interests once the underlying MQTT data is older than a configurable threshold (simulating a producer/device going offline)
- Signed NDN Data Packets via `pyndn`'s `KeyChain`

## Prerequisites

- Ubuntu 22.04 LTS (tested on two VirtualBox VMs)
- Python 3.8+
- [ndn-cxx](https://github.com/named-data/ndn-cxx) and [NFD](https://github.com/named-data/NFD) built from source
- [ndn-tools](https://github.com/named-data/ndn-tools) (optional, for `ndnping`/`ndnpingserver` testing)
- Mosquitto broker (`mosquitto`, `mosquitto-clients`)
- Python packages:
  ```bash
  pip install paho-mqtt PyNDN2 --break-system-packages
  ```

## Network Setup

| Node              | Adapter 1 (Bridged)        | Adapter 2 (Internal Network) | Role                  |
|-------------------|-----------------------------|-------------------------------|------------------------|
| VM 1 (Gateway)    | DHCP (e.g., `192.168.1.x`)  | `10.10.10.1/24`                | Mosquitto Broker, Gateway |
| VM 2 (Consumer)   | —                            | `10.10.10.2/24`                | Consumer Node          |

See [`docs/setup.md`](docs/setup.md) for full instructions on installing NFD, configuring netplan, creating Ethernet Faces, and registering Routes between the two VMs.

## Usage

### 1. Start the MQTT broker (VM 1)

```bash
sudo systemctl start mosquitto
```

### 2. Start NFD (both VMs)

```bash
nfd-start
```

### 3. Run the gateway (VM 1)

```bash
python3 ndn_gateway_simple.py
```

By default, the gateway:
- Connects to `localhost:1883`, topic `sensor/room1/data`
- Registers the NDN prefix `/sensor/room1`
- Caches each Data Packet for `10000` ms (configurable via `setFreshnessPeriod()`)
- Stops answering Interests if no MQTT data has been received in the last `DATA_STALE_THRESHOLD` seconds (default: 5s)

### 4. Run the consumer (VM 2)

```bash
python3 ndn_consumer_simple.py
```

The consumer polls `/sensor/room1/temperature` and `/sensor/room1/humidity` every second (configurable via `INTERVAL` in `main()`) and prints each response or timeout.

## NDN Naming Scheme

```
/sensor
  /room1
    /temperature
    /humidity
```

- **Specific request:** `/sensor/room1/temperature` — fetch a single value.
- **Collective request:** `/sensor/room1` — leverages NDN's Longest Prefix Match for broader queries.

## Testing

**Check Content Store hit/miss ratio:**
```bash
nfdc cs info
```

**Ping the producer prefix directly:**
```bash
# On VM 1 (producer side)
ndnpingserver /sensor/room1

# On VM 2 (consumer side)
ndnping /sensor/room1
```

**Inspect Faces and Routes:**
```bash
nfdc face list
nfdc route list
```

## Project Structure

```
.
├── ndn_gateway_simple.py    # MQTT -> NDN translation gateway (VM 1)
├── ndn_consumer_simple.py   # NDN consumer application (VM 2)
└── README.md
```

## Notes

This project was built as part of a final-year academic project (Tugas Akhir) at Telkom University, in collaboration with the TIP (Telecom Infra Project) Community Lab, exploring NDN as a transitional architecture for existing IoT hardware.

