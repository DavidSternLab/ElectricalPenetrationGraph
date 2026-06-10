"""Stream consumer: parse device frames and dispatch to a recorder + live callbacks.

Transport-agnostic — feed it byte chunks from anything (mock device, pyserial, a socket).
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from . import protocol as P
from .recorder import HDF5Recorder


class StreamConsumer:
    def __init__(self, recorder: Optional[HDF5Recorder] = None,
                 on_block: Optional[Callable[[P.SampleBlock], None]] = None,
                 on_event: Optional[Callable[[P.Event], None]] = None,
                 on_info: Optional[Callable[[P.Info], None]] = None):
        self.parser = P.FrameParser()
        self.recorder = recorder
        self.on_block = on_block
        self.on_event = on_event
        self.on_info = on_info
        self.info: Optional[P.Info] = None
        self.n_blocks = 0
        self.n_samples = 0
        self.n_events = 0

    def feed(self, chunk: bytes) -> None:
        for mtype, _flags, payload in self.parser.feed(chunk):
            if mtype == P.T_SAMPLES:
                blk = P.SampleBlock.decode(payload)
                self.n_blocks += 1
                self.n_samples += len(blk.samples)
                if self.recorder:
                    self.recorder.add_block(blk)
                if self.on_block:
                    self.on_block(blk)
            elif mtype == P.T_EVENT:
                ev = P.Event.decode(payload)
                self.n_events += 1
                if self.recorder:
                    self.recorder.add_event(ev)
                if self.on_event:
                    self.on_event(ev)
            elif mtype == P.T_INFO:
                self.info = P.Info.decode(payload)
                if self.on_info:
                    self.on_info(self.info)
            # ACK/NACK/STATUS ignored here

    def feed_all(self, chunks: Iterable[bytes]) -> None:
        for c in chunks:
            self.feed(c)
