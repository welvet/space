#ifndef SPACE_SWITCHES_H
#define SPACE_SWITCHES_H

#include <Arduino.h>
#include <Servo.h>
#include <string.h>

#include "generated_config.h"

namespace space {

class Switches {
 public:
  void loop() {
    const unsigned long now = millis();
    for (int index = 0; index < SWITCH_COUNT; ++index) {
      if (active_[index] && now - startedAt_[index] >= SERVO_SETTLE_MS) {
        servos_[index].detach();
        active_[index] = false;
      }
    }
  }

  void move(const char* id, const char* position) {
    for (int index = 0; index < SWITCH_COUNT; ++index) {
      if (strcmp(SWITCHES[index].id, id) != 0) continue;

      const int angle = strcmp(position, "straight") == 0
          ? SWITCHES[index].straightAngle
          : SWITCHES[index].divergeAngle;
      if (servos_[index].attach(SWITCHES[index].pin) == 0) return;
      servos_[index].write(angle);
      active_[index] = true;
      startedAt_[index] = millis();
      return;
    }
  }

 private:
  Servo servos_[SWITCH_STORAGE_SIZE];
  bool active_[SWITCH_STORAGE_SIZE] = {false};
  unsigned long startedAt_[SWITCH_STORAGE_SIZE] = {0};
};

}  // namespace space

#endif
