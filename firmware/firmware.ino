#include "connection.h"
#include "readers.h"
#include "switches.h"

void tagChanged(
    int reader,
    bool detected,
    const uint8_t* uid,
    uint8_t uidLength);

space::Switches switches;
space::Readers readers(tagChanged);
space::Connection connection(switches, readers);

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  readers.setup();
  connection.setup();
}

void loop() {
  connection.loop();
  switches.loop();
  readers.loop();
}

void tagChanged(
    int reader,
    bool detected,
    const uint8_t* uid,
    uint8_t uidLength) {
  connection.sendTag(reader, detected, uid, uidLength);
}
