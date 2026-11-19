#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys

run = Path(__file__).resolve().parent
root = run.parents[3]
sys.path.insert(0, str(root / "sources/rom/rom-build/tools"))
from lp_probe import SparseReader, parse_geometry, parse_metadata

parts_dir = next(root.glob("ColorOS16_*/super-parts-32m"))
parts = json.loads((parts_dir / "manifest.json").read_text())["parts"]
def mounted_part(record):
    path = parts_dir / record["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    return path.open("rb")

with mounted_part(parts[0]) as first:
    sparse = SparseReader(first, verbose=False)
    prefix = sparse.read_range(0, 1024*1024, chunk_limit=sparse.total_chunks)
metadata = parse_metadata(prefix, parse_geometry(prefix))
partitions = {p["name"]: p for p in metadata["partitions"]}
print({name: row["size_bytes"] for name,row in partitions.items()})
for name in sys.argv[1:]:
    row = partitions[name]
    with (run / f"c16-{name}.img").open("xb") as output:
        for extent in row["extents"]:
            assert extent["type"] == extent["source"] == 0
            start = extent["target_data"] * 512
            end = start + extent["sectors"] * 512
            written = 0
            for part in parts:
                low = max(start, part["start"])
                high = min(end, part["start"] + part["raw_bytes"])
                if high <= low:
                    continue
                with mounted_part(part) as stream:
                    sparse = SparseReader(stream, verbose=False)
                    data = sparse.read_range(low, high - low, chunk_limit=sparse.total_chunks)
                    assert len(data) == high - low
                    output.write(data)
                    written += len(data)
            assert written == end - start
