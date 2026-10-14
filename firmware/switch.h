#pragma once

#include "device.h"
#include "generated_config.h"

inline void deviceTask(void*) {
  uint32_t sequence = 0;
  int angle = 0;
  bool powered = false;
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
  JsonDocument stateMessage;
  stateMessage["ready"] = true;
  stateMessage["pin"] = SERVO_PIN;
  stateMessage["power"] = powered;
  stateMessage["angle"] = angle;
  publishState(stateMessage, sequence);

  DeviceCommand command;
  for (;;) {
    if (xQueueReceive(commands, &command, portMAX_DELAY) != pdTRUE) continue;
    JsonDocument message;
    if (deserializeJson(message, command.payload)) continue;
    const char* error = nullptr;
    JsonArray operations = message["commands"].as<JsonArray>();
    if (strcmp(message["cmd"] | "", "batch") != 0 || operations.isNull() || operations.size() == 0) {
      error = "Expected a nonempty command batch";
    } else {
      for (JsonVariant operation : operations) {
        const char* cmd = operation["cmd"] | "";
        if (!operation["value"].is<int>()) {
          error = "Command value must be an integer";
          break;
        }
        const int value = operation["value"];
        if (!((strcmp(cmd, "power") == 0 && (value == 0 || value == 1)) ||
              (strcmp(cmd, "rotate") == 0 && value >= -90 && value <= 90) ||
              (strcmp(cmd, "sleep") == 0 && value >= 0))) {
          error = "Invalid command or value";
          break;
        }
      }
    }
    if (!error) {
      stateMessage.remove("error");
      for (JsonVariant operation : operations) {
        const char* cmd = operation["cmd"];
        const int value = operation["value"];
        if (strcmp(cmd, "sleep") == 0) {
          uint32_t remaining = value;
          while (remaining) {
            const uint32_t duration = min(remaining, uint32_t(60000));
            vTaskDelay(max(TickType_t(1), pdMS_TO_TICKS(duration)));
            remaining -= duration;
          }
          continue;
        }
        if (strcmp(cmd, "power") == 0) {
          if (value && !powered) {
            if (!ledcAttach(SERVO_PIN, 50, 16)) {
              error = "Servo PWM initialization failed";
              break;
            }
            powered = true;
          } else if (!value && powered) {
            ledcDetach(SERVO_PIN);
            pinMode(SERVO_PIN, OUTPUT);
            digitalWrite(SERVO_PIN, LOW);
            powered = false;
          }
        } else {
          angle = value;
        }
        if (powered) {
          const uint32_t pulseUs = 1000 + (angle + 90) * 1000 / 180;
          ledcWrite(SERVO_PIN, pulseUs * 65535UL / 20000UL);
        }
        stateMessage["power"] = powered;
        stateMessage["angle"] = angle;
        stateMessage.remove("error");
        publishState(stateMessage, sequence);
      }
    }
    if (error) {
      stateMessage["error"] = error;
      publishState(stateMessage, sequence);
    } else {
      publishState(stateMessage, sequence);
    }
  }
}
