"""Display detrend tests (needs numpy)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from epgrig.dsp import OnePoleHighPass, moving_average_detrend


def test_moving_average_removes_dc_offset():
    fs = 1000
    t = np.arange(fs) / fs
    x = 0.5 + 0.01 * np.sin(2 * np.pi * 20 * t)   # 20 Hz signal on a big DC offset
    y = moving_average_detrend(x, window=fs // 2)
    assert abs(y.mean()) < 1e-3                    # DC removed
    assert y.std() > 0.005                         # signal preserved


def test_onepole_highpass_kills_slow_ramp_keeps_fast():
    fs = 1000.0
    t = np.arange(2000) / fs
    ramp = 0.2 * t                                  # slow drift
    fast = 0.01 * np.sin(2 * np.pi * 30 * t)        # 30 Hz signal
    x = (ramp + fast).reshape(-1, 1)
    hp = OnePoleHighPass(fs, fc=1.0, n_channels=1)
    y = hp.process(x)[:, 0]
    tail = y[1000:]                                 # after settling
    # 1st-order HP leaves a residual ~ slope/(2*pi*fc); the un-filtered ramp would be ~0.3 V,
    # so require strong attenuation rather than exact zero.
    assert abs(tail.mean()) < 0.05                  # slow ramp strongly suppressed (~10x)
    assert tail.std() > 0.003                       # fast component survives


def test_onepole_shape_and_streaming_continuity():
    fs = 1000.0
    hp = OnePoleHighPass(fs, fc=0.5, n_channels=3)
    a = hp.process(np.ones((100, 3)))
    b = hp.process(np.ones((100, 3)))
    assert a.shape == (100, 3) and b.shape == (100, 3)
    # constant input -> output decays toward 0 (high-pass), continuous across blocks
    assert abs(b[-1]).max() < abs(a[0]).max() + 1e-9


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  PASS {fn.__name__}")
    print(f"All {len(fns)} dsp tests passed.")


if __name__ == "__main__":
    _run()
