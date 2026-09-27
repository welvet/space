#ifndef SPACE_CONNECTION_H
#define SPACE_CONNECTION_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFiS3.h>
#include <string.h>

#include "generated_config.h"
#include "readers.h"
#include "switches.h"

namespace space {

class Connection {
 public:
  Connection(Switches& switches, Readers& readers)
      : switches_(switches), readers_(readers) {}

  void setup() {
    connectWifi();
  }

  void loop() {
    updateWifi();
    updateBackend();
    readCommands();
  }

  void sendTag(
      int reader,
      bool detected,
      const uint8_t* uid,
      uint8_t uidLength) {
    char tag[3 * 7] = {0};
    formatUid(uid, uidLength, tag, sizeof(tag));

    JsonDocument message;
    message["event"] = detected ? "tag_detected" : "tag_removed";
    message["hub"] = HUB_ID;
    message["detector"] = READERS[reader].id;
    message["tag_id"] = tag;
    send(message);

    Serial.print(READERS[reader].id);
    Serial.print(detected ? " detected " : " removed ");
    Serial.println(tag);
  }

 private:
  static constexpr size_t kLineSize = 256;

  Switches& switches_;
  Readers& readers_;
  WiFiClient client_;
  bool wifiConnected_ = false;
  bool backendConnected_ = false;
  unsigned long lastWifiAttempt_ = 0;
  unsigned long lastBackendAttempt_ = 0;
  char line_[kLineSize] = {0};
  size_t lineLength_ = 0;
  bool lineOverflowed_ = false;

  void updateWifi() {
    const bool connected = WiFi.status() == WL_CONNECTED;
    if (connected != wifiConnected_) {
      wifiConnected_ = connected;
      Serial.println(connected ? "wifi connected" : "wifi disconnected");
      if (connected) connectBackend();
      else disconnectBackend();
    }

    if (!connected && millis() - lastWifiAttempt_ >= RECONNECT_MS) {
      connectWifi();
    }
  }

  void connectWifi() {
    lastWifiAttempt_ = millis();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }

  void updateBackend() {
    if (backendConnected_ && !client_.connected()) {
      backendConnected_ = false;
      Serial.println("backend disconnected");
    }
    if (!wifiConnected_ || backendConnected_) return;
    if (millis() - lastBackendAttempt_ >= RECONNECT_MS) connectBackend();
  }

  void connectBackend() {
    lastBackendAttempt_ = millis();
    if (!wifiConnected_ || !client_.connect(BACKEND_HOST, BACKEND_PORT)) return;
    backendConnected_ = true;
    Serial.println("backend connected");
    sendHello();
  }

  void disconnectBackend() {
    client_.stop();
    if (backendConnected_) Serial.println("backend disconnected");
    backendConnected_ = false;
    lineLength_ = 0;
    lineOverflowed_ = false;
  }

  void readCommands() {
    while (client_.available()) {
      const char value = client_.read();
      if (value == '\n') {
        if (!lineOverflowed_ && lineLength_ > 0) {
          line_[lineLength_] = '\0';
          handle(line_);
        }
        lineLength_ = 0;
        lineOverflowed_ = false;
      } else if (!lineOverflowed_ && lineLength_ < kLineSize - 1) {
        line_[lineLength_++] = value;
      } else {
        lineLength_ = 0;
        lineOverflowed_ = true;
      }
    }
  }

  void handle(const char* line) {
    JsonDocument message;
    if (deserializeJson(message, line)) return;
    if (strcmp(message["cmd"] | "", "move") != 0) return;
    const char* id = message["switch"];
    const char* position = message["position"];
    if (id != nullptr && position != nullptr) switches_.move(id, position);
  }

  void sendHello() {
    JsonDocument message;
    message["event"] = "hello";
    message["hub"] = HUB_ID;

    JsonArray switches = message["switches"].to<JsonArray>();
    for (int index = 0; index < SWITCH_COUNT; ++index) {
      switches.add(SWITCHES[index].id);
    }

    JsonArray detectors = message["detectors"].to<JsonArray>();
    JsonArray detectedTags = message["detected_tags"].to<JsonArray>();
    for (int index = 0; index < READER_COUNT; ++index) {
      if (!readers_.ready(index)) continue;
      detectors.add(READERS[index].id);
      if (!readers_.present(index)) continue;

      char tag[3 * 7] = {0};
      formatUid(
          readers_.uid(index),
          readers_.uidLength(index),
          tag,
          sizeof(tag));
      JsonObject detected = detectedTags.add<JsonObject>();
      detected["detector"] = READERS[index].id;
      detected["tag_id"] = tag;
    }
    send(message);
  }

  void send(JsonDocument& message) {
    if (!client_.connected()) return;
    serializeJson(message, client_);
    client_.println();
  }

  static void formatUid(
      const uint8_t* uid,
      uint8_t uidLength,
      char* output,
      size_t size) {
    size_t offset = 0;
    for (uint8_t index = 0; index < uidLength && offset + 3 < size; ++index) {
      if (index > 0) output[offset++] = ':';
      offset += snprintf(output + offset, size - offset, "%02X", uid[index]);
    }
    output[offset] = '\0';
  }
};

}  // namespace space

#endif
