"""Incremental, crash-safe HDF5 recorder (see docs/protocol-and-data-format.md §B)."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

import h5py
import numpy as np

from . import protocol as P

FORMAT_VERSION = "0.1"

_EVENT_DT = np.dtype([
    ("sample_index", "<u8"),
    ("time_s", "<f8"),
    ("type", "<i4"),
    ("channel", "<i2"),
    ("a", "<i4"),
    ("b", "<i4"),
    ("text", h5py.string_dtype()),
])


class HDF5Recorder:
    def __init__(self, path: str, info: P.Info, sample_rate_hz: int,
                 channel_mask: int, *, metadata: Optional[dict] = None,
                 compression: str = "gzip", flush_every_s: float = 1.0):
        self.path = path
        self.info = info
        self.rate = sample_rate_hz
        self.channel_mask = channel_mask
        self.chans = P.active_channels(channel_mask)
        self.nch = len(self.chans)
        self.n_samples = 0
        self.n_events = 0
        self._since_flush = 0
        self._flush_every = max(1, int(flush_every_s * sample_rate_hz))
        # device sample_index of this file's row 0; lets recording start mid-stream while
        # keeping file event indices 0-based (so the reader's reconstruction stays correct).
        self.start_sample_index: Optional[int] = None

        self.h5 = h5py.File(path, "w")
        a = self.h5.attrs
        a["format_version"] = FORMAT_VERSION
        a["device_serial"] = info.serial
        a["firmware_version"] = f"{info.fw_major}.{info.fw_minor}.{info.fw_patch}"
        a["start_time_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        a["sample_rate_hz"] = sample_rate_hz
        a["n_channels"] = self.nch
        a["channel_mask"] = channel_mask
        a["adc_bits"] = info.adc_bits
        a["adc_vref_v"] = info.adc_vref_mv / 1000.0
        a["fixed_gain"] = info.fixed_gain
        a["vs_range_mv"] = info.vs_range_mv
        a["vs_dac_bits"] = info.vs_dac_bits
        for k, v in (metadata or {}).items():
            a[k] = v

        chunk_rows = max(1, min(sample_rate_hz, 4096))
        self.samples = self.h5.create_dataset(
            "samples", shape=(0, self.nch), maxshape=(None, self.nch),
            dtype="<i4", chunks=(chunk_rows, self.nch), compression=compression)
        self.samples.attrs["channel_ids"] = np.array(self.chans, dtype="i4")
        self.samples.attrs["code_to_volts_adc"] = (info.adc_vref_mv / 1000.0) / (1 << 23)
        self.samples.attrs["adc_to_input_referred"] = 1.0 / info.fixed_gain

        self.events = self.h5.create_dataset(
            "events", shape=(0,), maxshape=(None,), dtype=_EVENT_DT,
            chunks=(256,), compression=compression)

    # -- ingest -------------------------------------------------------------
    def add_block(self, blk: P.SampleBlock) -> None:
        if not blk.samples:
            return
        if self.start_sample_index is None:
            self.start_sample_index = blk.first_sample_index
        arr = np.asarray(blk.samples, dtype="<i4")
        n = arr.shape[0]
        self.samples.resize(self.n_samples + n, axis=0)
        self.samples[self.n_samples:self.n_samples + n, :] = arr
        self.n_samples += n
        self._since_flush += n
        if self._since_flush >= self._flush_every:
            self.h5.flush()
            self._since_flush = 0

    def add_event(self, ev: P.Event) -> None:
        if self.start_sample_index is None:
            self.start_sample_index = ev.sample_index
        rel = max(0, ev.sample_index - self.start_sample_index)  # file-relative index
        self.events.resize(self.n_events + 1, axis=0)
        self.events[self.n_events] = (
            rel, rel / self.rate, ev.event_type,
            (-1 if ev.channel == P.CHAN_DEVICE else ev.channel), ev.a, ev.b, ev.text)
        self.n_events += 1

    def add_comment(self, text: str, sample_index: int, channel: int = P.CHAN_DEVICE) -> None:
        self.add_event(P.Event(P.EV_COMMENT, channel, sample_index, text=text))

    def close(self) -> None:
        if self.h5:
            self.h5.attrs["n_samples"] = self.n_samples
            self.h5.attrs["duration_s"] = self.n_samples / self.rate
            self.h5.attrs["device_start_sample_index"] = (
                self.start_sample_index if self.start_sample_index is not None else 0)
            self.h5.flush()
            self.h5.close()
            self.h5 = None

    def __enter__(self) -> "HDF5Recorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
