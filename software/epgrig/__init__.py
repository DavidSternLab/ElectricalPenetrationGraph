"""epgrig — host-side software for the redesigned EPG rig.

Layers (all transport-agnostic, GUI optional):
  protocol     COBS+CRC framing and message codecs (pure stdlib)
  mock_device  in-process synthetic device speaking the protocol
  acquisition  parse device frames -> recorder + live callbacks
  recorder     incremental crash-safe HDF5 writer
  reader       HDF5 reader + signal reconstruction
"""
from . import protocol  # noqa: F401

__version__ = "0.1.0"
