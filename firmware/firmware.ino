#include "connection.h"
#include "selected_task.h"
#include <esp_system.h>

QueueHandle_t events;
QueueHandle_t state;
QueueHandle_t commands;
std::atomic<uint32_t> readerPolls{0};
TaskHandle_t deviceTaskHandle = nullptr;
Connection connection;

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  if (DEVICE_LOGS) Serial.printf("[boot] %s reset_reason=%d\n", DEVICE_TYPE, static_cast<int>(esp_reset_reason()));
  events = xQueueCreate(32, sizeof(DeviceState));
  state = xQueueCreate(1, sizeof(DeviceState));
  commands = xQueueCreate(8, sizeof(DeviceCommand));
  if (!events || !state || !commands) abort();
  DeviceState initial = {};
  strcpy(initial.payload, "{\"ready\":false}");
  xQueueOverwrite(state, &initial);
  if (xTaskCreate(deviceTask, "Device", 8192, nullptr, 1, &deviceTaskHandle) != pdPASS) abort();
  connection.setup();
}

void loop() {
  connection.loop();
  static unsigned long lastDiagnostics = 0;
  const unsigned long now = millis();
  if (DEVICE_LOGS && now - lastDiagnostics >= 5000) {
    lastDiagnostics = now;
    Serial.printf("[memory] uptime_ms=%lu heap_free=%u heap_min=%u device_stack_min=%u reader_polls=%lu\n",
        now, ESP.getFreeHeap(), ESP.getMinFreeHeap(),
        static_cast<unsigned int>(uxTaskGetStackHighWaterMark(deviceTaskHandle)),
        static_cast<unsigned long>(readerPolls.load(std::memory_order_relaxed)));
  }
  delay(1);
}
