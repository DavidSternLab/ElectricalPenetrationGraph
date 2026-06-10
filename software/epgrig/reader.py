"""Reader + reconstruction for EPG HDF5 recordings (see docs §B.3).

Conventions:
    input_referred_volts = code * (vref/2^23) / fixed_gain
    applied Vs at sample i = value of the most recent VS_CHANGE with index <= i
    uncompensated (Vs-removed) signal = input_referred - applied_Vs
The as-recorded trace is `input_referred` directly; display detrending is a view only.
"""
from __future__ import annotations

from dataclasses import dataclass

import h5py
import numpy as np

from . import protocol as P


@dataclass
class Recording:
    rate_hz: float
    channel_ids: np.ndarray          # physical channel index per column
    codes: np.ndarray                # int32 [n, nch]
    code_to_volts_adc: float
    fixed_gain: float
    vs_range_mv: float
    vs_dac_bits: int
    events: np.ndarray               # structured array
    attrs: dict

    @property
    def n_samples(self) -> int:
        return self.codes.shape[0]

    @property
    def t(self) -> np.ndarray:
        return np.arange(self.n_samples) / self.rate_hz

    @property
    def input_referred(self) -> np.ndarray:
        """Volts referred to the probe input (as recorded, servo-corrected)."""
        return self.codes.astype(np.float64) * self.code_to_volts_adc / self.fixed_gain

    def _dac_to_vs(self, code: int) -> float:
        half = self.vs_range_mv / 2000.0
        return code / ((1 << self.vs_dac_bits) - 1) * (2 * half) - half

    def applied_vs(self) -> np.ndarray:
        """Reconstruct the applied Vs (volts) per sample/channel from VS_CHANGE events."""
        n, nch = self.codes.shape
        vs = np.zeros((n, nch))
        col = {int(c): k for k, c in enumerate(self.channel_ids)}
        # gather VS_CHANGE events sorted by sample_index
        ev = self.events
        mask = ev["type"] == P.EV_VS_CHANGE
        order = np.argsort(ev["sample_index"][mask], kind="stable")
        idxs = ev["sample_index"][mask][order]
        chs = ev["channel"][mask][order]
        newdac = ev["b"][mask][order]
        for si, ch, nd in zip(idxs, chs, newdac):
            if ch == -1:  # device-wide (unused for Vs); skip
                continue
            if ch not in col:
                continue
            k = col[ch]
            vs[int(si):, k] = self._dac_to_vs(int(nd))
        return vs

    def uncompensated(self) -> np.ndarray:
        """Input-referred signal with the applied Vs removed (continuous biological + drift)."""
        return self.input_referred - self.applied_vs()

    def events_as_dicts(self) -> list[dict]:
        out = []
        for r in self.events:
            out.append({
                "sample_index": int(r["sample_index"]),
                "time_s": float(r["time_s"]),
                "type": P.EVENT_NAMES.get(int(r["type"]), int(r["type"])),
                "channel": int(r["channel"]),
                "a": int(r["a"]), "b": int(r["b"]),
                "text": r["text"].decode() if isinstance(r["text"], bytes) else str(r["text"]),
            })
        return out


def load(path: str) -> Recording:
    with h5py.File(path, "r") as f:
        s = f["samples"]
        rec = Recording(
            rate_hz=float(f.attrs["sample_rate_hz"]),
            channel_ids=np.array(s.attrs["channel_ids"]),
            codes=s[()],
            code_to_volts_adc=float(s.attrs["code_to_volts_adc"]),
            fixed_gain=float(f.attrs["fixed_gain"]),
            vs_range_mv=float(f.attrs["vs_range_mv"]),
            vs_dac_bits=int(f.attrs["vs_dac_bits"]),
            events=f["events"][()],
            attrs={k: f.attrs[k] for k in f.attrs},
        )
    return rec
