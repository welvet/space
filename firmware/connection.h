#pragma once

#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include <esp_mac.h>

#include "device.h"
#include "generated_config.h"

class Connection {
 public:
  void setup() {
    uint8_t mac[6];
    if (esp_efuse_mac_get_default(mac) != ESP_OK) abort();
    snprintf(deviceId_, sizeof(deviceId_), "%s_%02X%02X%02X%02X%02X%02X",
        DEVICE_TYPE, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    if (DEVICE_LOGS) Serial.printf("[device] %s\n", deviceId_);
    hostname_ = deviceId_;
    hostname_.replace("_", "-");
    hostname_.toLowerCase();
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }

  void loop() {
    const wl_status_t wifiStatus = WiFi.status();
    if (wifiStatus != lastWifiStatus_) {
      lastWifiStatus_ = wifiStatus;
      if (DEVICE_LOGS) Serial.printf("[wifi] status=%d ip=%s\n", wifiStatus, WiFi.localIP().toString().c_str());
    }
    if (wifiStatus != WL_CONNECTED) {
      client_.stop();
      if (mdnsReady_) MDNS.end();
      mdnsReady_ = false;
      connected_ = false;
      clearCommands();
      discardEvents();
      return;
    }
    if (!mdnsReady_) {
      mdnsReady_ = MDNS.begin(hostname_);
      if (DEVICE_LOGS) Serial.printf("[mdns] started=%d\n", mdnsReady_);
    }
    if (!client_.connected()) {
      if (connected_ && DEVICE_LOGS) Serial.println("[backend] disconnected");
      client_.stop();
      connected_ = false;
      clearCommands();
      discardEvents();
      if (!mdnsReady_ || millis() - lastAttempt_ < RECONNECT_MS) return;
      lastAttempt_ = millis();
      if (!connectBackend()) return;
      connected_ = true;
      if (DEVICE_LOGS) Serial.println("[backend] connected");
      lastPong_ = millis();
      lastPing_ = lastPong_ - kPingIntervalMs;
      DeviceState current = {};
      xQueuePeek(state, &current, 0);
      lastSequence_ = current.sequence;
      JsonDocument hello;
      deserializeJson(hello, current.payload);
      hello["event"] = "hello";
      hello["device"] = deviceId_;
      hello["type"] = DEVICE_TYPE;
      send(hello);
    }

    readCommands();
    heartbeat();
    DeviceState event;
    while (connected_ && xQueueReceive(events, &event, 0) == pdTRUE) {
      if (event.sequence <= lastSequence_) continue;
      lastSequence_ = event.sequence;
      JsonDocument message;
      deserializeJson(message, event.payload);
      message["event"] = "state";
      message["device"] = deviceId_;
      send(message);
    }
  }

 private:
  static constexpr unsigned long kPingIntervalMs = 10000;
  static constexpr unsigned long kReplyTimeoutMs = 30000;

  char deviceId_[sizeof(DEVICE_TYPE) + 13] = {};
  String hostname_;
  WiFiClient client_;
  wl_status_t lastWifiStatus_ = WL_NO_SHIELD;
  bool mdnsReady_ = false;
  bool connected_ = false;
  unsigned long lastAttempt_ = 0;
  unsigned long lastPing_ = 0;
  unsigned long lastPong_ = 0;
  uint32_t lastSequence_ = 0;
  DeviceCommand command_ = {};
  size_t lineLength_ = 0;

  bool connectBackend() {
    mdns_result_t* results = nullptr;
    const esp_err_t result = mdns_query_ptr("_space", "_tcp", 3000, 20, &results);
    if (DEVICE_LOGS) Serial.printf("[mdns] query=%s\n", esp_err_to_name(result));
    if (result != ESP_OK) return false;
    bool connected = false;
    for (mdns_result_t* service = results; service && !connected; service = service->next) {
      for (mdns_ip_addr_t* address = service->addr; address; address = address->next) {
        if (address->addr.type != ESP_IPADDR_TYPE_V4) continue;
        const IPAddress ip(address->addr.u_addr.ip4.addr);
        if (DEVICE_LOGS) Serial.printf("[backend] trying %s:%u\n", ip.toString().c_str(), service->port);
        if (client_.connect(ip, service->port, 1000)) {
          connected = true;
          break;
        }
      }
    }
    mdns_query_results_free(results);
    return connected;
  }

  void heartbeat() {
    if (!connected_) return;
    const unsigned long now = millis();
    if (now - lastPong_ >= kReplyTimeoutMs) {
      if (DEVICE_LOGS) Serial.println("[heartbeat] pong timeout");
      client_.stop();
      connected_ = false;
      clearCommands();
      return;
    }
    if (now - lastPing_ >= kPingIntervalMs) {
      lastPing_ = now;
      JsonDocument ping;
      ping["event"] = "ping";
      if (DEVICE_LOGS) Serial.println("[heartbeat] ping");
      send(ping);
    }
  }

  void clearCommands() {
    lineLength_ = 0;
    DeviceCommand discarded;
    while (xQueueReceive(commands, &discarded, 0) == pdTRUE) {}
  }

  void readCommands() {
    while (connected_ && client_.available()) {
      const char value = client_.read();
      if (value == '\n') {
        command_.payload[lineLength_] = '\0';
        JsonDocument message;
        if (!deserializeJson(message, command_.payload)) {
          if (strcmp(message["event"] | "", "pong") == 0) {
            lastPong_ = millis();
            if (DEVICE_LOGS) Serial.println("[heartbeat] pong");
          } else if (message["cmd"].is<const char*>()) {
            if (xQueueSend(commands, &command_, 0) != pdTRUE) {
              client_.stop();
              connected_ = false;
            }
          }
        }
        lineLength_ = 0;
      } else if (lineLength_ < sizeof(command_.payload) - 1) {
        command_.payload[lineLength_++] = value;
      } else {
        client_.stop();
        connected_ = false;
        lineLength_ = 0;
      }
    }
  }

  void discardEvents() {
    DeviceState discarded;
    while (xQueueReceive(events, &discarded, 0) == pdTRUE) {}
  }

  void send(JsonDocument& message) {
    char line[384];
    const size_t size = serializeJson(message, line, sizeof(line) - 1);
    line[size] = '\n';
    if (client_.write(reinterpret_cast<const uint8_t*>(line), size + 1) != size + 1) {
      client_.stop();
      connected_ = false;
    }
  }
};
