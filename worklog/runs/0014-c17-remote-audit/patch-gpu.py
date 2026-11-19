#!/usr/bin/env python3
"""Add null-safe dispatch to the donor PreCache transactions."""
from hashlib import sha256
from pathlib import Path

run = Path(__file__).resolve().parent
source = run.parents[2] / "trees/system_ext/lib64/libgpuserviceextimpl.so"
donor = source.read_bytes()
assert sha256(donor).hexdigest() == "0e664704c359ed308bb119dd89eb09542f36f53d8621a5ff0b2ccdb960e64394"
assembled = (run / "gpu-precache-dispatch.bin").read_bytes()
base = 0x220a0  # sh_addr equals sh_offset for the donor .text.
output = bytearray(donor)
for offset, length in ((0x14, 48), (0xB8, 24), (0xE8, 16), (0x118, 16)):
    assert offset + length <= len(assembled)
    output[base + offset:base + offset + length] = assembled[offset:offset + length]
assert len(output) == len(donor)
(run / source.name).write_bytes(output)
print(sha256(output).hexdigest())
