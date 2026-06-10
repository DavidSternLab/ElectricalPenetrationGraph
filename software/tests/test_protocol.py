"""Protocol-layer tests: COBS, CRC, framing, message round-trips, parser resync.

Pure stdlib (no numpy/h5py needed). Run with: python -m pytest, or python tests/test_protocol.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epgrig import protocol as P


def test_cobs_roundtrip_random():
    rng = random.Random(0)
    for _ in range(500):
        n = rng.randint(0, 600)
        data = bytes(rng.randint(0, 255) for _ in range(n))
        enc = P.cobs_encode(data)
        assert 0 not in enc, "COBS output must not contain zero bytes"
        assert P.cobs_decode(enc) == data


def test_cobs_edge_cases():
    for data in [b"", b"\x00", b"\x00\x00", b"\x01\x02\x03",
                 b"\xff" * 300, bytes(range(256)) * 3]:
        assert P.cobs_decode(P.cobs_encode(data)) == data


def test_crc_known_and_changes():
    a = P.crc16(b"123456789")
    assert isinstance(a, int) and 0 <= a <= 0xFFFF
    assert P.crc16(b"123456789") == a            # deterministic
    assert P.crc16(b"123456780") != a            # sensitive to content


def test_frame_roundtrip():
    payload = b"hello \x00 world \xff"
    frame = P.encode_frame(P.T_EVENT, payload, flags=3)
    assert frame.endswith(b"\x00")
    t, fl, p = P.decode_frame(frame[:-1])
    assert (t, fl, p) == (P.T_EVENT, 3, payload)


def test_i24_roundtrip():
    for v in [0, 1, -1, 8388607, -8388608, 12345, -999999]:
        assert P.unpack_i24(P.pack_i24(v)) == v


def test_sampleblock_roundtrip():
    blk = P.SampleBlock(block_seq=7, first_sample_index=1000, rate_code=2,
                        channel_mask=0b10110001, status=1,
                        samples=[[100, -200, 300, 8388607],
                                 [-8388608, 0, 1, -1]])
    out = P.SampleBlock.decode(blk.encode())
    assert out.block_seq == 7 and out.first_sample_index == 1000
    assert out.channel_mask == 0b10110001 and out.status == 1
    assert out.samples == blk.samples


def test_event_roundtrip():
    ev = P.Event(P.EV_VS_CHANGE, 3, 54321, a=10, b=-20, text="track")
    out = P.Event.decode(ev.encode())
    assert (out.event_type, out.channel, out.sample_index, out.a, out.b, out.text) == \
           (P.EV_VS_CHANGE, 3, 54321, 10, -20, "track")
    assert out.type_name == "VS_CHANGE"


def test_info_roundtrip():
    info = P.Info(serial="EPG-XYZ-9", supported_rates=(500, 1000, 4000), fixed_gain_x100=800)
    out = P.Info.decode(info.encode())
    assert out.serial == "EPG-XYZ-9"
    assert out.supported_rates == (500, 1000, 4000)
    assert abs(out.fixed_gain - 8.0) < 1e-9


def test_parser_multiple_frames_and_resync():
    frames = b"".join(P.encode_frame(P.T_EVENT, bytes([i]) * (i + 1)) for i in range(5))
    parser = P.FrameParser()
    # corrupt: drop a byte in the middle of the stream to force a CRC error + resync
    corrupt = frames[:10] + frames[11:]
    got = list(parser.feed(corrupt))
    # at least the later frames after the corruption point must survive
    assert len(got) >= 3
    # the corruption is detected (bad CRC or bad COBS) and the parser resyncs
    assert (parser.crc_errors + parser.cobs_errors) >= 1
    # a clean follow-up frame parses fine on the same parser
    more = list(parser.feed(P.encode_frame(P.T_EVENT, b"clean")))
    assert more and more[0][2] == b"clean"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"All {len(fns)} protocol tests passed.")


if __name__ == "__main__":
    _run()
