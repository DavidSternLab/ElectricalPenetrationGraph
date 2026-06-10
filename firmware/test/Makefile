CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -O2
PROTO = ../proto/epg_proto.c

test_proto: test_proto.c $(PROTO) ../proto/epg_proto.h
	$(CC) $(CFLAGS) -o $@ test_proto.c $(PROTO)

.PHONY: check interop clean
check: test_proto
	./test_proto selftest

# cross-language interop with the Python codec
interop: test_proto
	python3 interop_test.py

clean:
	rm -f test_proto /tmp/c_frames.bin /tmp/py_frames.bin
