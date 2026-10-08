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
    hostname_ = deviceId_;
    hostname_.replace("_", "-");
    hostname_.toLowerCase();
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }

  void loop() {
    if (WiFi.status() != WL_CONNECTED) {
      client_.stop();
      if (mdnsReady_) MDNS.end();
      mdnsReady_ = false;
      connected_ = false;
      clearCommands();
      discardEvents();
      return;
    }
    if (!mdnsReady_) mdnsReady_ = MDNS.begin(hostname_);
    if (!client_.connected()) {
      client_.stop();
      connected_ = false;
      clearCommands();
      discardEvents();
      if (!mdnsReady_ || millis() - lastAttempt_ < RECONNECT_MS) return;
      lastAttempt_ = millis();
      const int count = MDNS.queryService("space", "tcp");
      for (int i = 0; i < count; ++i) {
        if (client_.connect(MDNS.address(i), MDNS.port(i), 1000)) break;
      }
      if (!client_.connected()) return;
      connected_ = true;
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
  char deviceId_[sizeof(DEVICE_TYPE) + 13] = {};
  String hostname_;
  WiFiClient client_;
  bool mdnsReady_ = false;
  bool connected_ = false;
  unsigned long lastAttempt_ = 0;
  uint32_t lastSequence_ = 0;
  DeviceCommand command_ = {};
  size_t lineLength_ = 0;

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
        if (!deserializeJson(message, command_.payload) && message["cmd"].is<const char*>()) {
          if (xQueueSend(commands, &command_, 0) != pdTRUE) {
            client_.stop();
            connected_ = false;
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
