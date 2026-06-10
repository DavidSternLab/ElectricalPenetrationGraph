"""Per-channel command handling in the mock device (no GUI needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from epgrig import protocol as P
from epgrig.mock_device import MockDevice


def _collect(dev, n):
    """Generate n samples, return (events, sample_rows) parsed from the wire frames."""
    parser = P.FrameParser()
    events, rows = [], []
    for fr in dev.generate_block(n):
        for mtype, _f, payload in parser.feed(fr):
            if mtype == P.T_EVENT:
                events.append(P.Event.decode(payload))
            elif mtype == P.T_SAMPLES:
                rows.extend(P.SampleBlock.decode(payload).samples)
    return events, rows


def test_servo_and_ri_change_emit_events():
    dev = MockDevice(seed=1, channel_mask=0b0001, rate_hz=1000)
    dev.handle_command(P.T_SERVO, 0, bytes([0, P.SERVO_OFF, 0, 0, 0, 0, 0]))
    dev.handle_command(P.T_SET_RI, 0, bytes([0, P.RI_10T]))
    events, _ = _collect(dev, 10)
    kinds = {e.event_type for e in events}
    assert P.EV_SERVO_STATE in kinds and P.EV_RI_CHANGE in kinds
    servo_ev = next(e for e in events if e.event_type == P.EV_SERVO_STATE)
    assert servo_ev.a == P.SERVO_OFF
    ri_ev = next(e for e in events if e.event_type == P.EV_RI_CHANGE)
    assert ri_ev.a == P.RI_10T
    assert dev._servo_mode[0] == P.SERVO_OFF and dev._ri[0] == P.RI_10T


def test_set_vs_emits_change_and_moves_baseline():
    dev = MockDevice(seed=1, channel_mask=0b0001, rate_hz=1000)
    dev.handle_command(P.T_SERVO, 0, bytes([0, P.SERVO_OFF, 0, 0, 0, 0, 0]))
    # set Vs to +100 mV
    dac = int(round((0.100 + 0.5) / 1.0 * ((1 << 16) - 1)))
    dev.handle_command(P.T_SET_VS, 0, bytes([0]) + dac.to_bytes(2, "little"))
    events, rows = _collect(dev, 200)
    vs_ev = [e for e in events if e.event_type == P.EV_VS_CHANGE]
    assert vs_ev and vs_ev[0].text == "manual"
    # with servo off and +100 mV Vs, output baseline is strongly positive
    mean_code = np.mean([r[0] for r in rows])
    assert mean_code > 0.05 * (1 << 23)


def test_cal_pulse_on_off_and_signal_dip():
    dev = MockDevice(seed=3, channel_mask=0b0001, rate_hz=1000)
    dev.handle_command(P.T_SERVO, 0, bytes([0, P.SERVO_OFF, 0, 0, 0, 0, 0]))
    dev.handle_command(P.T_CAL_PULSE, 0, bytes([0, 1]) + (200).to_bytes(2, "little"))
    events, rows = _collect(dev, 500)  # 500 ms: pulse on for 200 ms then auto-off
    cal = [e for e in events if e.event_type == P.EV_CAL_PULSE]
    actions = [e.a for e in cal]
    assert 1 in actions and 0 in actions          # both onset and auto-offset logged
    during = np.mean([r[0] for r in rows[20:180]])  # inside the pulse
    after = np.mean([r[0] for r in rows[300:480]])   # after it ends
    assert during < after                          # −50 mV injection pulls the signal down


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  PASS {fn.__name__}")
    print(f"All {len(fns)} command tests passed.")


if __name__ == "__main__":
    _run()
