"""Display-side signal processing.

The hardware Vs servo only acts to prevent clipping (D11); the *display* is centered
in software here. Detrending is a VIEW only — raw codes are always what gets recorded.
"""
from __future__ import annotations

import numpy as np


def moving_average_detrend(x: np.ndarray, window: int) -> np.ndarray:
    """Subtract a centered moving-average baseline (a simple, fast high-pass for display).

    x: 1-D or 2-D [n] / [n, ch]. window in samples (≈ fs / cutoff_hz).
    """
    x = np.asarray(x, dtype=np.float64)
    if window <= 1:
        return x - x.mean(axis=0, keepdims=True)
    if x.ndim == 1:
        return x - _boxcar(x, window)
    return x - np.stack([_boxcar(x[:, k], window) for k in range(x.shape[1])], axis=1)


def _boxcar(x: np.ndarray, window: int) -> np.ndarray:
    window = min(window, len(x)) or 1
    c = np.cumsum(np.insert(x, 0, 0.0))
    avg = (c[window:] - c[:-window]) / window
    # pad edges so output length == input length, baseline held at the ends
    pad_l = window // 2
    pad_r = len(x) - len(avg) - pad_l
    return np.concatenate([np.full(pad_l, avg[0]), avg, np.full(max(pad_r, 0), avg[-1])])[:len(x)]


class OnePoleHighPass:
    """Streaming first-order high-pass for live display, per channel.

    y[n] = a*(y[n-1] + x[n] - x[n-1]),  a = exp(-2*pi*fc/fs)
    Removes slow baseline drift so traces stay centered on screen in real time.
    """

    def __init__(self, fs: float, fc: float, n_channels: int = 1):
        self.a = float(np.exp(-2 * np.pi * fc / fs))
        self.n = n_channels
        self._xprev = np.zeros(n_channels)
        self._yprev = np.zeros(n_channels)
        self._init = False

    def process(self, block: np.ndarray) -> np.ndarray:
        """block: [n_samples, n_channels] -> detrended copy (same shape)."""
        block = np.asarray(block, dtype=np.float64)
        out = np.empty_like(block)
        a = self.a
        xprev, yprev = self._xprev.copy(), self._yprev.copy()
        if not self._init:
            xprev = block[0].copy()
            self._init = True
        for i in range(block.shape[0]):
            x = block[i]
            y = a * (yprev + x - xprev)
            out[i] = y
            xprev, yprev = x, y
        self._xprev, self._yprev = xprev, yprev
        return out
