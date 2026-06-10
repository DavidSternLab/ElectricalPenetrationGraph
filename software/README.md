# epgrig — host software (Python)

Cross-platform acquisition + analysis for the redesigned EPG rig. Implements the
device↔host protocol and HDF5 recording format in [../docs/protocol-and-data-format.md](../docs/protocol-and-data-format.md),
and ships an **in-process mock device** so the entire pipeline runs and is tested
**before any hardware exists**.

## Layout
```
epgrig/
  protocol.py     COBS+CRC framing + message codecs   (pure stdlib — always importable)
  mock_device.py  synthetic device: aphid-like waveforms, electrode drift, Vs servo
  acquisition.py  parse device frames -> recorder + live callbacks (transport-agnostic)
  recorder.py     incremental crash-safe HDF5 writer
  reader.py       HDF5 reader + signal reconstruction (codes->volts, applied-Vs)
  dsp.py          display-side detrend (high-pass) — view only, never recorded
  gui.py          live pyqtgraph display (optional Qt)
scripts/
  record_mock.py  headless end-to-end demo: mock -> frames -> HDF5 -> reconstruct
  run_gui.py      launch the live GUI against the mock
tests/            protocol + pipeline tests (run with no hardware)
```

## Quick start
```bash
pip install -r requirements.txt          # numpy + h5py minimum; Qt only for the GUI

# headless end-to-end (no hardware, no Qt):
python scripts/record_mock.py /tmp/epg.h5 --seconds 30 --rate 1000

# tests:
python tests/test_protocol.py            # pure stdlib
python tests/test_pipeline.py            # needs numpy + h5py
# (or: python -m pytest)

# live GUI against the mock (needs pyqtgraph + a Qt binding):
python scripts/run_gui.py --rate 1000
```

## Design notes
- **Protocol layer is dependency-free** (stdlib only) so framing is trivially testable and
  portable; numpy/h5py are only needed for the data path, Qt only for the GUI.
- **Reconstructability:** recordings store raw 24-bit codes + a timestamped event log; the
  reader recovers input-referred volts and the applied-Vs trace, so the true signal is
  recoverable even though the keep-in-range servo nudges Vs during recording.
- **Real hardware later** drops in behind the same protocol: replace the mock's byte stream
  with a `pyserial` port (USB CDC). Nothing else changes.
