#pragma once

#include <Adafruit_PN532.h>
#include <SPI.h>
#include <string.h>

#include "device.h"
#include "generated_config.h"

inline void publishReader(bool ready, bool present, const char* tag, uint32_t& sequence) {
  JsonDocument message;
  message["ready"] = ready;
  if (present) message["tag_id"] = tag;
  else message["tag_id"] = nullptr;
  publishState(message, sequence);
}

inline void deviceTask(void*) {
  SPI.begin(18, 19, 23, 5);
  Adafruit_PN532 reader(5, &SPI);
  reader.begin();
  bool ready = false;
  bool present = false;
  char tag[21] = {};
  uint32_t sequence = 0;
  unsigned long lastSeen = 0;

  for (;;) {
    if (!ready) {
      ready = reader.getFirmwareVersion() != 0 && reader.SAMConfig() &&
          reader.setPassiveActivationRetries(0x01);
      if (!ready) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        continue;
      }
      publishReader(ready, present, tag, sequence);
    }

    uint8_t uid[7] = {};
    uint8_t length = 0;
    const bool found = reader.readPassiveTargetID(
        PN532_MIFARE_ISO14443A, uid, &length, READ_TIMEOUT_MS);
    bool nextPresent = present;
    char nextTag[21];
    strcpy(nextTag, tag);
    if (found) {
      lastSeen = millis();
      nextPresent = true;
      size_t offset = 0;
      for (uint8_t i = 0; i < length && i < sizeof(uid); ++i) {
        if (i) nextTag[offset++] = ':';
        offset += snprintf(nextTag + offset, sizeof(nextTag) - offset, "%02X", uid[i]);
      }
      nextTag[offset] = '\0';
    } else if (present && millis() - lastSeen >= REMOVAL_DELAY_MS) {
      nextPresent = false;
    }

    if (nextPresent != present || strcmp(nextTag, tag) != 0) {
      present = nextPresent;
      strcpy(tag, nextTag);
      publishReader(ready, present, tag, sequence);
    }
    DeviceCommand command;
    while (xQueueReceive(commands, &command, 0) == pdTRUE) {
      publishReader(ready, present, tag, sequence);
    }

    vTaskDelay(pdMS_TO_TICKS(1));
  }
}
