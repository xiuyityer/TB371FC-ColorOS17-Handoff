#!/usr/bin/env python3
"""Assemble the release from partition bytes verified against the test tablet."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

run = Path(__file__).resolve().parent
workspace = run.parents[2]
release = workspace / "releases/TB371FC-C17-KSU-20261118"
runs = run.parent
block = 4096
span = 32 * 1024 * 1024 - block


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(8 << 20), b""):
            digest.update(data)
    return digest.hexdigest()


def encode(raw, start, total):
    chunks = []
    for kind, size, data in (
        (0xCAC3, start, b""),
        (0xCAC2, len(raw), bytes(4)) if not any(raw) else (0xCAC1, len(raw), raw),
        (0xCAC3, total - start - len(raw), b""),
    ):
        if size:
            chunks.append(struct.pack("<HHII", kind, 0, size // block, 12 + len(data)) + data)
    header = struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, block,
                         total // block, len(chunks), 0)
    return header + b"".join(chunks)


def readback(data, start, size, total):
    magic, major, minor, header, chunk_header, blk, blocks, chunks, checksum = struct.unpack_from(
        "<IHHHHIIII", data
    )
    assert (magic, major, minor, header, chunk_header, blk, blocks, checksum) == (
        0xED26FF3A, 1, 0, 28, 12, block, total // block, 0
    )
    cursor = 0
    decoded = None
    for _ in range(chunks):
        kind, reserved, count, stored = struct.unpack_from("<HHII", data, header)
        payload = data[header + chunk_header:header + stored]
        length = count * block
        assert reserved == 0
        if kind == 0xCAC3:
            assert not payload
        else:
            assert decoded is None and cursor == start and length == size
            if kind == 0xCAC1:
                assert len(payload) == length
                decoded = payload
            else:
                assert kind == 0xCAC2 and payload == bytes(4)
                decoded = bytes(length)
        cursor += length
        header += stored
    assert cursor == total and header == len(data) and decoded is not None
    return decoded


def main():
    overrides = {
        "system_a": runs / "0014-c17-remote-audit/system-a-integrated.img",
        "system_ext_a": runs / "0017-c17-camera-connect/system-ext-a-radio-lookup.img",
        "vendor_a": runs / "0020-c17-shared-data/vendor-a-c17-shared-data.img",
        "my_product_a": runs / "0021-c17-pen-refresh/my-product-a-system-ui-144.img",
    }
    source = json.loads((workspace / "rom-r1/super.json").read_text())
    total = source["bytes"]
    live = dict(re.findall(r"^([a-f0-9]{64})  /dev/block/mapper/(\w+)$",
                           (run / "device-dynamic-before.txt").read_text(), re.M))
    live = {name: digest for digest, name in live.items()}
    partitions = []
    for entry in source["inputs"]:
        name = entry["name"]
        image = overrides.get(name, Path(entry["image"]))
        assert image.stat().st_size == entry["bytes"]
        digest = sha(image)
        assert digest == live[name], (name, digest, live[name])
        partitions.append(dict(name=name, offset=entry["offset"], bytes=entry["bytes"],
                               sha256=digest, source=str(image.relative_to(workspace))))
    assert set(live) == {item["name"] for item in partitions}
    prefix = (workspace / "rom-r1/super-metadata.bin").read_bytes()
    assert len(prefix) == partitions[0]["offset"] == 1 << 20
    assert hashlib.sha256(prefix).hexdigest() == (run / "device-super-prefix.txt").read_text().split()[0]

    out = release / "super"
    assert not (release / "manifest.json").exists()
    out.mkdir(exist_ok=True)
    image_hash = hashlib.sha256()
    parts = []
    embedded = {item["name"]: hashlib.sha256() for item in partitions}
    with ExitStack() as stack:
        images = {item["name"]: stack.enter_context((workspace / item["source"]).open("rb"))
                  for item in partitions}
        for n, start in enumerate(range(0, total, span)):
            end = min(start + span, total)
            data = bytearray(end - start)
            if start == 0:
                data[:len(prefix)] = prefix
            for item in partitions:
                name = item["name"]
                offset = item["offset"]
                low, high = max(start, offset), min(end, offset + item["bytes"])
                if low < high:
                    image = images[name]
                    image.seek(low - offset)
                    result = image.read(high - low)
                    assert len(result) == high - low
                    data[low-start:high-start] = result

            file = out / f"super.part{n:04d}.sparse.img"
            file.write_bytes(encode(data, start, total))
            packed = file.read_bytes()
            restored = readback(packed, start, len(data), total)
            assert restored == data and len(packed) <= 32 << 20
            image_hash.update(restored)
            for item in partitions:
                offset = item["offset"]
                low, high = max(start, offset), min(end, offset + item["bytes"])
                if low < high:
                    embedded[item["name"]].update(restored[low-start:high-start])
            parts.append(dict(file=str(file.relative_to(release)), start=start, raw_bytes=len(data),
                              bytes=len(packed), sha256=hashlib.sha256(packed).hexdigest()))
    for item in partitions:
        assert embedded[item["name"]].hexdigest() == item["sha256"], item["name"]

    files = {}
    for name, source, expected in (
        ("boot_a.img", runs / "0010-c17-ringbuf-kernel/boot_a.img",
         (run / "device-boot-before.txt").read_text().splitlines()[0]),
        ("recovery_a.img", workspace / "twrp/twrp_3.7.1.img",
         "6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7"),
        ("apps/KernelSU-32720.apk", workspace / "donor/KernelSU_v3.3.1-40_32720-release.apk",
         "aa445d3da3d05f0e0dcc9ebc107706b9a694e7bfac8ce4c40877898797d3b095"),
        ("apps/ZUI-Camera.apk", runs / "0017-c17-camera-connect/c16-ZuiCamera.apk",
         "0c72c201cef16bb4e187257690d7963b3c49c13dfa990ebb3cc1b53da57e7b7e"),
    ):
        target = release / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        assert sha(target) == expected
        files[name] = dict(bytes=target.stat().st_size, sha256=expected)
    result = dict(format=1, product="spinel", slot="a", super_bytes=total,
                  super_sha256=image_hash.hexdigest(), recovery_partition_bytes=104857600,
                  parts=parts, files=files, logical_partitions=partitions)
    (release / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{len(parts)} sparse images, {sum(p['bytes'] for p in parts):,} file bytes")
    print(f"Super expanded SHA-256 {result['super_sha256']}")


if __name__ == "__main__":
    main()
