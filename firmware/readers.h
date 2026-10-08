#ifndef SPACE_READERS_H
#define SPACE_READERS_H

#include <Adafruit_PN532.h>
#include <Arduino.h>
#include <SPI.h>
#include <string.h>

#include "generated_config.h"

namespace space {

class Readers {
 public:
  using Callback = void (*)(
      int reader,
      bool detected,
      const uint8_t* uid,
      uint8_t uidLength);

  explicit Readers(Callback callback) : callback_(callback) {}

  void setup() {
    if (READER_COUNT == 0) return;

    SPI.begin();
    for (int index = 0; index < READER_COUNT; ++index) {
      pinMode(READERS[index].ssPin, OUTPUT);
      digitalWrite(READERS[index].ssPin, HIGH);
    }
    for (int index = 0; index < READER_COUNT; ++index) {
      devices_[index] = new Adafruit_PN532(READERS[index].ssPin, &SPI);
      devices_[index]->begin();
      ready_[index] =
          devices_[index]->getFirmwareVersion() != 0 && devices_[index]->SAMConfig();
      if (ready_[index]) scan(index, false);
    }
  }

  void loop() {
    for (int index = 0; index < READER_COUNT; ++index) scan(index, true);
  }

  bool ready(int index) const { return ready_[index]; }
  bool present(int index) const { return present_[index]; }
  const uint8_t* uid(int index) const { return uids_[index]; }
  uint8_t uidLength(int index) const { return uidLengths_[index]; }

 private:
  Callback callback_;
  Adafruit_PN532* devices_[READER_STORAGE_SIZE] = {nullptr};
  bool ready_[READER_STORAGE_SIZE] = {false};
  bool present_[READER_STORAGE_SIZE] = {false};
  uint8_t uids_[READER_STORAGE_SIZE][7] = {{0}};
  uint8_t uidLengths_[READER_STORAGE_SIZE] = {0};
  unsigned long lastSeenAt_[READER_STORAGE_SIZE] = {0};

  void scan(int index, bool publish) {
    if (!ready_[index]) return;

    uint8_t uid[7] = {0};
    uint8_t uidLength = 0;
    const ReaderConfig& config = READERS[index];
    const bool detected = devices_[index]->readPassiveTargetID(
        PN532_MIFARE_ISO14443A,
        uid,
        &uidLength,
        config.readTimeoutMs);
    const unsigned long now = millis();

    if (detected) {
      lastSeenAt_[index] = now;
      if (!present_[index] || !sameUid(index, uid, uidLength)) {
        uidLengths_[index] = min(uidLength, static_cast<uint8_t>(7));
        memcpy(uids_[index], uid, uidLengths_[index]);
        present_[index] = true;
        if (publish) callback_(index, true, uids_[index], uidLengths_[index]);
      }
      return;
    }

    if (present_[index] && now - lastSeenAt_[index] >= config.removalDelayMs) {
      if (publish) callback_(index, false, uids_[index], uidLengths_[index]);
      present_[index] = false;
      uidLengths_[index] = 0;
    }
  }

  bool sameUid(int index, const uint8_t* uid, uint8_t length) const {
    return length == uidLengths_[index] &&
        memcmp(uid, uids_[index], length) == 0;
  }
};

}  // namespace space

#endif
