#!/usr/bin/env python3
"""Launch the live GUI (mock device by default). Requires pyqtgraph + a Qt binding."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epgrig.gui import run_mock_gui


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=1000)
    ap.add_argument("--channels", type=lambda x: int(x, 0), default=0xFF)
    ap.add_argument("--detrend-fc", type=float, default=0.5, help="display high-pass cutoff (Hz)")
    args = ap.parse_args()
    run_mock_gui(rate_hz=args.rate, channel_mask=args.channels, detrend_fc=args.detrend_fc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
