#include <Arduino_FreeRTOS.h>

#include "connection.h"
#include "readers.h"
#include "switches.h"

AUTOSTART_FREERTOS

void tagChanged(
    int reader,
    bool detected,
    const uint8_t* uid,
    uint8_t uidLength);

space::Switches switches;
space::Readers readers(tagChanged);
space::Connection connection(switches, readers);

void detectorLoop(void*) {
  for (;;) readers.loop();
}

void setup() {
  readers.setup();
  connection.setup();
  xTaskCreate(
      detectorLoop,
      "Detectors",
      1024 / 4,
      nullptr,
      4,
      nullptr);
}

void loop() {
  connection.loop();
  switches.loop();
  taskYIELD();
}

void tagChanged(
    int reader,
    bool detected,
    const uint8_t* uid,
    uint8_t uidLength) {
  connection.sendTag(reader, detected, uid, uidLength);
}
