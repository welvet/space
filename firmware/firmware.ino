#include "connection.h"
#include "selected_task.h"

QueueHandle_t events;
QueueHandle_t state;
QueueHandle_t commands;
Connection connection;

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  if (DEVICE_LOGS) Serial.printf("[boot] %s\n", DEVICE_TYPE);
  events = xQueueCreate(32, sizeof(DeviceState));
  state = xQueueCreate(1, sizeof(DeviceState));
  commands = xQueueCreate(8, sizeof(DeviceCommand));
  if (!events || !state || !commands) abort();
  DeviceState initial = {};
  strcpy(initial.payload, "{\"ready\":false}");
  xQueueOverwrite(state, &initial);
  if (xTaskCreate(deviceTask, "Device", 4096, nullptr, 1, nullptr) != pdPASS) abort();
  connection.setup();
}

void loop() {
  connection.loop();
  delay(1);
}
