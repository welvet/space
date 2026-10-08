#pragma once

#include "device.h"
#include "generated_config.h"

inline void deviceTask(void*) {
  uint32_t sequence = 0;
  JsonDocument message;
  message["ready"] = false;
  message["pin"] = MOTOR_PIN;
  message["error"] = "Motor driver not configured";
  publishState(message, sequence);

  DeviceCommand command;
  for (;;) {
    if (xQueueReceive(commands, &command, portMAX_DELAY) == pdTRUE) {
      publishState(message, sequence);
    }
  }
}
