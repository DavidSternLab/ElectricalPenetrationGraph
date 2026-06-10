/* Minimal ADS131M08 driver (8-ch, 24-bit, simultaneous-sampling Σ-Δ).
 * SKELETON: register addresses/sequences must be verified against the datasheet. */
#ifndef ADS131M08_H
#define ADS131M08_H

#include <Arduino.h>
#include <stdint.h>

class ADS131M08 {
public:
    void begin(int cs, int drdy, int reset);
    // Read one simultaneous sample set; fills ch[8] with signed 24-bit codes.
    // Returns true if a new frame was read.
    bool readFrame(int32_t ch[8]);
    bool dataReady() const { return digitalRead(_drdy) == LOW; }
private:
    int _cs, _drdy, _reset;
    uint32_t xfer24(uint32_t tx);
};

#endif
