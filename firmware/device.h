#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

struct DeviceState {
  uint32_t sequence;
  char payload[192];
};

struct DeviceCommand {
  char payload[256];
};

extern QueueHandle_t events;
extern QueueHandle_t state;
extern QueueHandle_t commands;

inline void publishState(JsonDocument& message, uint32_t& sequence) {
  DeviceState current = {};
  current.sequence = ++sequence;
  if (measureJson(message) >= sizeof(current.payload)) abort();
  serializeJson(message, current.payload, sizeof(current.payload));
  xQueueOverwrite(state, &current);
  if (xQueueSend(events, &current, 0) != pdTRUE) {
    DeviceState discarded;
    xQueueReceive(events, &discarded, 0);
    xQueueSend(events, &current, 0);
  }
}
