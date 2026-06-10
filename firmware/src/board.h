/* RP2040 pin map for the EPG motherboard (draft — verify against the PCB). */
#ifndef EPG_BOARD_H
#define EPG_BOARD_H

#include <Arduino.h>

// ADS131M08 (8-ch 24-bit ADC) on SPI0
static const int PIN_ADC_SCK   = 2;
static const int PIN_ADC_MOSI  = 3;
static const int PIN_ADC_MISO  = 4;
static const int PIN_ADC_CS    = 5;
static const int PIN_ADC_DRDY  = 6;   // active-low data-ready (IRQ)
static const int PIN_ADC_RESET = 7;

// DAC8568 (8-ch 16-bit, Vs per channel) — shares the SPI0 bus
static const int PIN_DAC_CS    = 8;
static const int PIN_DAC_LDAC  = 9;

// Ri (1 GΩ / 10 TΩ) latching relays driven via a 74HC595 shift-register chain
// (one bit pair per channel set/reset); keeps GPIO count low.
static const int PIN_SR_DATA   = 10;
static const int PIN_SR_CLK    = 11;
static const int PIN_SR_LATCH  = 12;

static const int N_CHANNELS    = 8;

#endif // EPG_BOARD_H
