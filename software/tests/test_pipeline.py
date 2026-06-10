"""End-to-end pipeline test: mock device -> frames -> recorder -> reader.

Needs numpy + h5py. Run: python tests/test_pipeline.py  (or via pytest)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from epgrig import protocol as P, reader
from epgrig.acquisition import StreamConsumer
from epgrig.mock_device import MockDevice
from epgrig.recorder import HDF5Recorder


def _record(seconds=3.0, rate=1000, mask=0b00001111, seed=2):
    dev = MockDevice(seed=seed, channel_mask=mask, rate_hz=rate)
    path = tempfile.mktemp(suffix=".h5")
    rec = HDF5Recorder(path, dev.info, rate, mask, metadata={"operator": "test"})
    consumer = StreamConsumer(recorder=rec)
    consumer.feed_all(dev.iter_stream(seconds))
    rec.close()
    return path, consumer, rate, seconds, mask


def test_sample_count_and_shape():
    path, consumer, rate, seconds, mask = _record()
    r = reader.load(path)
    expected = int(rate * seconds)
    assert consumer.n_samples == expected
    assert r.n_samples == expected
    assert r.codes.shape == (expected, bin(mask).count("1"))
    assert consumer.parser.crc_errors == 0
    os.remove(path)


def test_metadata_and_calibration():
    path, consumer, rate, seconds, mask = _record()
    r = reader.load(path)
    assert r.rate_hz == rate
    assert abs(r.fixed_gain - 8.0) < 1e-9
    assert r.attrs["operator"] in ("test", b"test")
    # input-referred conversion sane: within ADC range / gain
    assert np.all(np.abs(r.input_referred) < 1.2 / r.fixed_gain + 1e-6)
    os.remove(path)


def test_vs_events_and_reconstruction():
    # long enough that drift forces the keep-in-range servo to act at least once
    path, consumer, rate, seconds, mask = _record(seconds=20.0, seed=5)
    r = reader.load(path)
    evs = r.events_as_dicts()
    vs = [e for e in evs if e["type"] == "VS_CHANGE"]
    assert len(vs) >= 1, "expected at least one keep-in-range Vs step over 20 s of drift"
    # applied-Vs trace is piecewise-constant and changes at the event indices
    applied = r.applied_vs()
    assert applied.shape == r.codes.shape
    e0 = vs[0]
    si, ch = e0["sample_index"], e0["channel"]
    col = list(r.channel_ids).index(ch)
    # value just after the first step differs from the initial zero
    assert abs(applied[si, col]) > 0
    # uncompensated = input_referred - applied_vs (definitional)
    assert np.allclose(r.uncompensated(), r.input_referred - applied)
    os.remove(path)


def test_midstream_recording_offsets_are_file_relative():
    # simulate pressing Record after the device stream has already advanced
    info = P.Info()
    path = tempfile.mktemp(suffix=".h5")
    rec = HDF5Recorder(path, info, 1000, 0b0001)
    base = 5000
    rec.add_block(P.SampleBlock(0, base, 2, 0b0001, 0, [[10], [20], [30]]))
    rec.add_event(P.Event(P.EV_VS_CHANGE, 0, base + 1, a=32768, b=40000, text="track"))
    rec.add_block(P.SampleBlock(1, base + 3, 2, 0b0001, 0, [[40], [50]]))
    rec.close()

    r = reader.load(path)
    assert r.n_samples == 5
    assert int(r.attrs["device_start_sample_index"]) == base
    evs = r.events_as_dicts()
    assert evs[0]["sample_index"] == 1          # 5001 - 5000, file-relative
    applied = r.applied_vs()
    assert applied[0, 0] == 0 and applied[1, 0] != 0    # step takes effect at file row 1
    os.remove(path)


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"All {len(fns)} pipeline tests passed.")


if __name__ == "__main__":
    _run()
