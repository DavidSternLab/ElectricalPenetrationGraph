/* EPG rig — RP2040 firmware (Arduino-pico).  SKELETON / not yet hardware-tested.
 *
 * Implements the device side of the protocol in ../proto/epg_proto.{h,c} (the SAME codec
 * the host GUI uses — verified byte-for-byte by firmware/test/interop_test.py), so this
 * talks directly to software/epgrig over USB CDC.
 *
 * Pipeline: on ADC DRDY -> read 8 ch -> run keep-in-range Vs servo -> append to block;
 * flush a SAMPLES frame every BLOCK_MS; handle host commands; emit EVENT on every state
 * change (Vs/Ri/cal/servo) stamped with the current sample_index.
 */
#include <Arduino.h>
#include <SPI.h>
extern "C" {
#include "epg_proto.h"
}
#include "board.h"
#include "ads131m08.h"
#include "dac8568.h"

// ---- device identity / config ----
static const uint16_t RATES[] = {250, 500, 1000, 2000, 4000};
static epg_info_t INFO = { EPG_PROTO_VERSION, 0,1,0, N_CHANNELS,
                           1200, 800, 1000, 16, 24, RATES, 5, "EPG-RP2040-0001" };

static ADS131M08 adc;
static DAC8568   dac;

// runtime state
static volatile bool running = false;
static uint8_t  channel_mask = 0xFF;
static uint8_t  rate_code = 2;            // default 1000 Hz
static uint64_t sample_index = 0;
static uint32_t block_seq = 0;
static const float BLOCK_MS = 50.0f;

// per-channel state
static uint16_t vs_dac[N_CHANNELS];
static uint8_t  servo_mode[N_CHANNELS];
static uint8_t  ri_mode[N_CHANNELS];
static bool     cal_active[N_CHANNELS];
static uint32_t cal_until_ms[N_CHANNELS];
static float    baseline[N_CHANNELS];     // slow EMA of output code (servo)

// block accumulation
static int32_t  blk_samples[256][N_CHANNELS];
static uint16_t blk_n = 0;
static uint64_t blk_first = 0;
static uint8_t  blk_status = 0;
static uint32_t last_flush_ms = 0;

// ---- framing helpers ----
static void send_frame(uint8_t type, const uint8_t *payload, size_t plen) {
    uint8_t frame[600];
    size_t fl = epg_encode_frame(type, 0, payload, plen, frame);
    Serial.write(frame, fl);
}
static void emit_event(uint8_t etype, uint8_t ch, int32_t a, int32_t b,
                       const char *text) {
    uint8_t pay[64];
    uint8_t tl = 0; while (text && text[tl] && tl < 40) tl++;
    size_t pl = epg_build_event(etype, ch, sample_index, a, b, text, tl, pay);
    send_frame(T_EVENT, pay, pl);
}
static void send_ack(uint8_t cmd) { uint8_t p[2]={cmd,0}; send_frame(T_ACK, p, 2); }

// ---- helpers ----
static int active_count() { return __builtin_popcount(channel_mask); }

static void set_vs(uint8_t ch, uint16_t dac_code, const char *reason) {
    uint16_t old = vs_dac[ch];
    vs_dac[ch] = dac_code;
    dac.writeChannel(ch, dac_code);
    emit_event(EV_VS_CHANGE, ch, old, dac_code, reason);
}

static void set_ri(uint8_t ch, uint8_t mode) {
    ri_mode[ch] = mode;
    // TODO: shift-register pulse to the channel's latching reed relay (set/reset).
    emit_event(EV_RI_CHANGE, ch, mode, 0, "");
}

// keep-in-range / acquire servo, mirroring the host mock (D11)
static void servo_step(uint8_t ch, int32_t code) {
    uint8_t m = servo_mode[ch];
    if (m == SERVO_OFF) return;
    baseline[ch] = 0.999f * baseline[ch] + 0.001f * (float)code;
    const float FS = 8388607.0f;
    float thresh = (m == SERVO_ACQUIRE) ? 0.30f : 0.80f;
    if (fabsf(baseline[ch]) > thresh * FS) {
        // step Vs DAC toward recentering (sign/scale set by hardware; placeholder gain)
        int32_t step = (int32_t)(-baseline[ch] / FS * 2000.0f);  // ~codes; TODO calibrate
        int32_t nd = (int32_t)vs_dac[ch] + step;
        if (nd < 0) nd = 0; if (nd > 65535) nd = 65535;
        set_vs(ch, (uint16_t)nd, (m == SERVO_ACQUIRE) ? "acquire" : "track");
        baseline[ch] = 0.0f;
    }
}

// ---- command handling ----
static void on_frame(uint8_t type, uint8_t flags, const uint8_t *p, size_t n, void *u) {
    (void)flags; (void)u;
    switch (type) {
        case T_GET_INFO: { uint8_t pay[128]; size_t pl = epg_build_info(&INFO, pay);
                           send_frame(T_INFO, pay, pl); break; }
        case T_CONFIGURE: if (n >= 2 && !running) { rate_code = p[0]; channel_mask = p[1]; }
                          send_ack(type); break;
        case T_START: running = true; sample_index = 0; block_seq = 0; blk_n = 0;
                      blk_first = 0; last_flush_ms = millis(); send_ack(type); break;
        case T_STOP:  running = false; send_ack(type); break;
        case T_SET_VS: { epg_set_vs_t c; if (epg_parse_set_vs(p,n,&c)) set_vs(c.ch,c.dac,"manual");
                         send_ack(type); break; }
        case T_SET_RI: { epg_set_ri_t c; if (epg_parse_set_ri(p,n,&c)) set_ri(c.ch,c.mode);
                         send_ack(type); break; }
        case T_CAL_PULSE: { epg_cal_t c; if (epg_parse_cal(p,n,&c)) {
                              if (c.action == 1) { cal_active[c.ch]=true;
                                  cal_until_ms[c.ch]=millis()+(c.dur_ms?c.dur_ms:500);
                                  emit_event(EV_CAL_PULSE,c.ch,1,-50000,""); }
                              else { cal_active[c.ch]=false; emit_event(EV_CAL_PULSE,c.ch,0,-50000,""); }
                          } send_ack(type); break; }
        case T_SERVO: { epg_servo_t c; if (epg_parse_servo(p,n,&c)) {
                          servo_mode[c.ch]=c.mode; emit_event(EV_SERVO_STATE,c.ch,c.mode,0,""); }
                        send_ack(type); break; }
        case T_PING: send_ack(type); break;
        default: { uint8_t p2[3]={type,0,1}; send_frame(T_NACK,p2,3); }
    }
}

static epg_parser_t parser;

void setup() {
    Serial.begin(115200);                 // USB CDC; baud ignored
    for (int i=0;i<N_CHANNELS;i++){ vs_dac[i]=32768; servo_mode[i]=SERVO_TRACK;
                                    ri_mode[i]=RI_1G; cal_active[i]=false; baseline[i]=0; }
    pinMode(PIN_SR_DATA,OUTPUT); pinMode(PIN_SR_CLK,OUTPUT); pinMode(PIN_SR_LATCH,OUTPUT);
    dac.begin(PIN_DAC_CS, PIN_DAC_LDAC);
    adc.begin(PIN_ADC_CS, PIN_ADC_DRDY, PIN_ADC_RESET);
    epg_parser_init(&parser, on_frame, nullptr);
}

static void flush_block() {
    if (blk_n == 0) return;
    uint8_t pay[8 + 256*3*N_CHANNELS];
    size_t pl = epg_build_sampleblock_header(block_seq++, blk_first, rate_code,
                                             channel_mask, blk_n, blk_status, pay);
    for (uint16_t r=0;r<blk_n;r++)
        for (int c=0;c<N_CHANNELS;c++)
            if (channel_mask & (1<<c)) { epg_pack_i24(blk_samples[r][c], pay+pl); pl+=3; }
    send_frame(T_SAMPLES, pay, pl);
    blk_n = 0; blk_status = 0;
}

void loop() {
    // 1) drain host commands
    while (Serial.available() > 0) {
        uint8_t b = (uint8_t)Serial.read();
        epg_parser_feed(&parser, &b, 1);
    }
    if (!running) return;

    // 2) acquire on data-ready
    if (adc.dataReady()) {
        int32_t ch[8];
        if (adc.readFrame(ch)) {
            if (blk_n == 0) blk_first = sample_index;
            for (int c=0;c<N_CHANNELS;c++) {
                blk_samples[blk_n][c] = ch[c];
                servo_step((uint8_t)c, ch[c]);
                if (cal_active[c] && (int32_t)(millis()-cal_until_ms[c]) >= 0) {
                    cal_active[c]=false; emit_event(EV_CAL_PULSE,c,0,-50000,"");
                }
            }
            blk_n++;
            sample_index++;
            if (blk_n >= 256) flush_block();
        }
    }

    // 3) periodic block flush
    if ((int32_t)(millis() - last_flush_ms) >= (int32_t)BLOCK_MS) {
        flush_block();
        last_flush_ms = millis();
    }
}
