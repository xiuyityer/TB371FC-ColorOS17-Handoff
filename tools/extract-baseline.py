#!/usr/bin/env python3
"""Recover byte-exact workspace inputs from the retained C17 clean flash ZIP."""
import argparse
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import struct
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
PREFIX = "TB371FC-C17-KSU-Clean-20261118"
BLOCK = 4096
SPARSE = struct.Struct("<IHHHHIIII")
CHUNK = struct.Struct("<HHII")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def file_hash(path):
    digest = sha256()
    with path.open("rb") as source:
        for data in iter(lambda: source.read(8 << 20), b""):
            digest.update(data)
    return digest.hexdigest()


def decode(blob, entry, expanded_size):
    start, size = entry["start"], entry["raw_bytes"]
    header = SPARSE.unpack_from(blob)
    count = header[-2]
    require(header == (0xED26FF3A, 1, 0, SPARSE.size, CHUNK.size, BLOCK,
                       expanded_size // BLOCK, count, 0), "Invalid sparse header")
    position, cursor, result = SPARSE.size, 0, None
    for _ in range(count):
        kind, reserved, blocks, stored = CHUNK.unpack_from(blob, position)
        length = blocks * BLOCK
        end = position + stored
        require(not reserved and CHUNK.size <= stored and end <= len(blob), "Invalid sparse chunk")
        payload = blob[position + CHUNK.size:end]
        if kind == 0xCAC3:
            require(not payload, "DONT_CARE chunk has payload")
        else:
            require(cursor == start and length == size and result is None, "Unexpected sparse extent")
            if kind == 0xCAC1:
                require(len(payload) == length, "Invalid RAW length")
                result = payload
            else:
                require(kind == 0xCAC2 and len(payload) == 4, "Invalid FILL payload")
                result = payload * (length // 4)
        cursor += length
        position = end
    require(cursor == expanded_size and position == len(blob) and result is not None,
            "Incomplete sparse part")
    return result


def extract(package, output, selected):
    manifest = json.loads((BASELINE / "manifest.json").read_text(encoding="utf-8"))
    expected_zip = (BASELINE / "release.sha256").read_text(encoding="utf-8").split()[0]
    require(file_hash(package) == expected_zip, "ZIP SHA-256 differs from the baseline")
    partitions = {p["name"] + ".img": (p["offset"], p["bytes"], p["sha256"])
                  for p in manifest["logical_partitions"]}
    # The first MiB contains the lab tablet's published super geometry and LP tables.
    metadata_digest = (BASELINE / "super-metadata.sha256").read_text().split()[0]
    partitions["super-metadata.bin"] = (0, 1 << 20, metadata_digest)
    files = manifest["files"]
    valid = set(partitions) | set(files)
    selected = set(selected) if selected else valid
    require(selected <= valid, f"Unknown selection: {', '.join(sorted(selected - valid))}")
    output.mkdir()
    logical = {name: row for name, row in partitions.items() if name in selected}
    with ZipFile(package) as source, ExitStack() as stack:
        base_manifest = json.loads(source.read(f"{PREFIX}/manifest.json"))
        require(all(base_manifest[key] == manifest[key] for key in ("parts", "files", "super_sha256")),
                "ZIP manifest differs from baseline")
        targets = {}
        for name in logical:
            targets[name] = stack.enter_context((output / name).open("xb"))
        for entry in manifest["parts"]:
            left, right = entry["start"], entry["start"] + entry["raw_bytes"]
            intersects = {}
            for name, (offset, size, _) in logical.items():
                start, end = max(left, offset), min(right, offset + size)
                if start < end:
                    intersects[name] = (start, end, offset)
            if not intersects:
                continue
            blob = source.read(f"{PREFIX}/{entry['file']}")
            require(len(blob) == entry["bytes"] and sha256(blob).hexdigest() == entry["sha256"],
                    f"Corrupt part {entry['file']}")
            image = decode(blob, entry, manifest["super_bytes"])
            for name, (start, end, offset) in intersects.items():
                targets[name].seek(start - offset)
                targets[name].write(image[start-left:end-left])
        for name, expected in files.items():
            if name in selected:
                data = source.read(f"{PREFIX}/{name}")
                require(len(data) == expected["bytes"] and sha256(data).hexdigest() == expected["sha256"],
                        f"Corrupt file {name}")
                path = output / name
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_bytes(data)
    for name, (_, size, digest) in logical.items():
        path = output / name
        require(path.stat().st_size == size and file_hash(path) == digest, f"Output hash differs: {name}")
    for name in sorted(selected):
        print(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("output", type=Path, help="new working directory")
    parser.add_argument("--only", action="append", help="output name, repeat as needed")
    args = parser.parse_args()
    extract(args.zip, args.output, args.only)


if __name__ == "__main__":
    main()
