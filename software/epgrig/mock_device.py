"""In-process mock EPG device.

Generates synthetic aphid-like EPG waveforms plus the slow electrode-potential drift,
runs the keep-in-range Vs servo (D11), and emits protocol frames (SampleBlock + Event)
exactly as the real device would. Used to develop and test the entire host pipeline
before hardware exists.

Signal model is input-referred volts:
    measured_in = signal(t) + electrode_drift(t) + Vs_applied
    output_code = round(gain * measured_in / vref * 2^23), clipped to ±(2^23-1)
The servo nudges Vs only when the slow baseline threatens to clip, emitting VS_CHANGE.
"""
from __future__ import annotations

import numpy as np

from . import protocol as P


class MockDevice:
    def __init__(self, *, seed: int = 0, channel_mask: int = 0xFF, rate_hz: int = 1000,
                 info: P.Info | None = None):
        self.info = info or P.Info()
        self.rate_hz = rate_hz
        self.channel_mask = channel_mask
        self.rng = np.random.default_rng(seed)
        self.chans = P.active_channels(channel_mask)

        self.vref = self.info.adc_vref_mv / 1000.0
        self.gain = self.info.fixed_gain
        self.full_scale = (1 << 23) - 1

        # per (physical) channel state
        self._drift = {c: self.rng.uniform(-0.05, 0.05) for c in self.chans}
        # slow directional electrode drift (V/s) — exaggerated vs real life so the
        # keep-in-range servo is exercised within short sessions
        self._drift_rate = {c: self.rng.choice([-1.0, 1.0]) * self.rng.uniform(0.008, 0.015)
                            for c in self.chans}
        self._phase = {c: self.rng.uniform(0, 2 * np.pi) for c in self.chans}
        self._vs = {c: 0.0 for c in self.chans}            # applied Vs, volts
        self._baseline = {c: 0.0 for c in self.chans}      # slow EMA of output volts
        self._clipped = {c: False for c in self.chans}
        # crude per-channel "waveform state machine": pathway vs potential-drop
        self._pd_until = {c: 0.0 for c in self.chans}
        # per-channel instrument state (settable by host commands)
        self._ri = {c: P.RI_1G for c in self.chans}
        self._servo_mode = {c: P.SERVO_TRACK for c in self.chans}
        self._cal_until = {c: 0.0 for c in self.chans}
        self._cal_active = {c: False for c in self.chans}

        self.sample_index = 0
        self.block_seq = 0
        self.running = False
        self._t = 0.0
        self._pending_events: list[P.Event] = []

    # -- command intake (host->device) -------------------------------------
    def handle_command(self, mtype: int, flags: int, payload: bytes) -> list[bytes]:
        """Process a host command; return frames to send back (ACK + INFO etc.)."""
        out = []
        if mtype == P.T_GET_INFO:
            out.append(P.encode_frame(P.T_INFO, self.info.encode()))
        elif mtype == P.T_CONFIGURE:
            rate_code, mask = payload[0], payload[1]
            self.rate_hz = self.info.supported_rates[rate_code]
            self.channel_mask = mask
            self.chans = P.active_channels(mask)
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_START:
            self.running = True
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_STOP:
            self.running = False
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_SET_VS:
            ch = payload[0]; dac = int.from_bytes(payload[1:3], "little")
            self._set_vs(ch, self._dac_to_vs(dac), reason="manual")
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_SET_RI:
            ch, mode = payload[0], payload[1]
            if ch in self._ri:
                self._ri[ch] = mode
                self._pending_events.append(
                    P.Event(P.EV_RI_CHANGE, ch, self.sample_index, a=mode))
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_CAL_PULSE:
            ch, action = payload[0], payload[1]
            dur_ms = int.from_bytes(payload[2:4], "little") if len(payload) >= 4 else 0
            if action == 1 and ch in self._cal_active:
                self._cal_active[ch] = True
                self._cal_until[ch] = self._t + (dur_ms / 1000.0 if dur_ms else 0.5)
                self._pending_events.append(
                    P.Event(P.EV_CAL_PULSE, ch, self.sample_index, a=1, b=-50000))
            elif ch in self._cal_active:
                self._cal_active[ch] = False
                self._pending_events.append(
                    P.Event(P.EV_CAL_PULSE, ch, self.sample_index, a=0, b=-50000))
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_SERVO:
            ch, mode = payload[0], payload[1]
            if ch in self._servo_mode:
                self._servo_mode[ch] = mode
                self._pending_events.append(
                    P.Event(P.EV_SERVO_STATE, ch, self.sample_index, a=mode))
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        elif mtype == P.T_PING:
            out.append(P.encode_frame(P.T_ACK, bytes([mtype, 0])))
        else:
            out.append(P.encode_frame(P.T_NACK, bytes([mtype, 0, 1])))
        return out

    # -- Vs / DAC helpers ---------------------------------------------------
    def _vs_to_dac(self, vs_v: float) -> int:
        half = self.info.vs_range_mv / 2000.0  # volts (±half)
        code = round((vs_v + half) / (2 * half) * ((1 << self.info.vs_dac_bits) - 1))
        return int(np.clip(code, 0, (1 << self.info.vs_dac_bits) - 1))

    def _dac_to_vs(self, code: int) -> float:
        half = self.info.vs_range_mv / 2000.0
        return code / ((1 << self.info.vs_dac_bits) - 1) * (2 * half) - half

    def _set_vs(self, ch: int, new_vs: float, reason: str) -> None:
        old = self._vs.get(ch, 0.0)
        self._vs[ch] = new_vs
        self._pending_events.append(P.Event(
            P.EV_VS_CHANGE, ch, self.sample_index,
            a=self._vs_to_dac(old), b=self._vs_to_dac(new_vs), text=reason))

    # -- signal generation --------------------------------------------------
    def _gen_input(self, ch: int, dt: float) -> float:
        # slow electrode drift: directional ramp + small random walk (rate-independent)
        self._drift[ch] += self._drift_rate[ch] * dt + self.rng.normal(0, 0.0008 * np.sqrt(dt))
        drift = self._drift[ch]
        # EPG-ish waveform
        if self._t < self._pd_until[ch]:
            wave = -0.04  # potential drop: ~ -40 mV plateau
        else:
            self._phase[ch] += 2 * np.pi * 4.0 * dt  # ~4 Hz pathway oscillation
            wave = 0.015 * np.sin(self._phase[ch])
            if self.rng.random() < 0.0005:            # occasionally trigger a pd
                self._pd_until[ch] = self._t + 0.5
        # calibration pulse: known −50 mV injected at the input while active
        cal = 0.0
        if self._cal_active[ch]:
            if self._t >= self._cal_until[ch]:
                self._cal_active[ch] = False
                self._pending_events.append(
                    P.Event(P.EV_CAL_PULSE, ch, self.sample_index, a=0, b=-50000))
            else:
                cal = -0.050
        noise = self.rng.normal(0, 30e-6)             # ~30 µV thermal floor
        return wave + drift + noise + cal

    def _servo(self, ch: int, out_v: float) -> None:
        mode = self._servo_mode.get(ch, P.SERVO_TRACK)
        if mode == P.SERVO_OFF:
            return
        # slow baseline estimate
        self._baseline[ch] = 0.999 * self._baseline[ch] + 0.001 * out_v
        fs_v = self.vref
        # acquire: snap aggressively toward center; track: keep-in-range only
        thresh = 0.30 if mode == P.SERVO_ACQUIRE else 0.80
        reason = "acquire" if mode == P.SERVO_ACQUIRE else "track"
        if abs(self._baseline[ch]) > thresh * fs_v:
            correction = -self._baseline[ch] / self.gain  # input-referred
            self._set_vs(ch, self._vs[ch] + correction, reason=reason)
            self._baseline[ch] = 0.0

    def _sample_channel(self, ch: int, dt: float) -> int:
        mi = self._gen_input(ch, dt) + self._vs[ch]
        out_v = self.gain * mi
        code = int(round(out_v / self.vref * self.full_scale))
        if code > self.full_scale or code < -self.full_scale:
            code = max(-self.full_scale, min(self.full_scale, code))
            if not self._clipped[ch]:
                self._clipped[ch] = True
                self._pending_events.append(P.Event(P.EV_CLIP, ch, self.sample_index, a=1))
        else:
            if self._clipped[ch]:
                self._clipped[ch] = False
                self._pending_events.append(P.Event(P.EV_CLIP, ch, self.sample_index, a=0))
        self._servo(ch, out_v)
        return code

    # -- streaming ----------------------------------------------------------
    def generate_block(self, n_samples: int) -> list[bytes]:
        """Advance the simulation by n_samples and return frames (events first, then block)."""
        dt = 1.0 / self.rate_hz
        rows = []
        first_idx = self.sample_index
        block_status = 0
        for _ in range(n_samples):
            row = [self._sample_channel(c, dt) for c in self.chans]
            if any(self._clipped.values()):
                block_status |= 1
            rows.append(row)
            self.sample_index += 1
            self._t += dt
        rate_code = self.info.supported_rates.index(self.rate_hz)
        frames = [P.encode_frame(P.T_EVENT, ev.encode()) for ev in self._pending_events]
        self._pending_events.clear()
        blk = P.SampleBlock(self.block_seq, first_idx, rate_code,
                            self.channel_mask, block_status, rows)
        frames.append(P.encode_frame(P.T_SAMPLES, blk.encode()))
        self.block_seq += 1
        return frames

    def iter_stream(self, duration_s: float, block_ms: float = 50.0):
        """Yield wire-byte chunks for a recording of the given duration (no real-time wait)."""
        n_per_block = max(1, int(self.rate_hz * block_ms / 1000.0))
        total = int(self.rate_hz * duration_s)
        produced = 0
        self.running = True
        while produced < total:
            n = min(n_per_block, total - produced)
            for fr in self.generate_block(n):
                yield fr
            produced += n
