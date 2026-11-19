#!/usr/bin/env python3
"""Encode exact covering sparse spans below the device's 32 MiB download limit."""
import hashlib
import json
from pathlib import Path
import struct

W = Path(__file__).resolve().parents[1]
report = json.loads((W/'rom-r1/super.json').read_text())
assert report['state'] == 'SUPER_ALL_EMBEDDED_IMAGES_READBACK_VERIFIED_HARDWARE_PENDING'
out = W/'rom-r1/super-parts-32m'
out.mkdir(exist_ok=False)
block = 4096
span = (32*1024*1024-128)//block*block
size = report['bytes']
rows = []
digest = hashlib.sha256()
with Path(report['image']).open('rb') as src:
    for index, start in enumerate(range(0, size, span)):
        raw = src.read(min(span, size-start))
        assert len(raw) == min(span, size-start)
        chunks = []
        def chunk(kind, blocks, payload=b''):
            if blocks:
                chunks.append(struct.pack('<HHII',kind,0,blocks,12+len(payload))+payload)
        chunk(0xcac3, start//block)
        if raw == bytes(len(raw)):
            chunk(0xcac2,len(raw)//block,bytes(4))
        else:
            chunk(0xcac1,len(raw)//block,raw)
        chunk(0xcac3,(size-start-len(raw))//block)
        encoded=struct.pack('<IHHHHIIII',0xed26ff3a,1,0,28,12,block,size//block,len(chunks),0)+b''.join(chunks)
        assert len(encoded) <= 32*1024*1024
        path=out/f'super.part{index:04d}.sparse.img'
        path.write_bytes(encoded)
        # Decode the saved file to independently check its span and full coverage.
        saved=path.read_bytes()
        pos=28
        cursor=0
        decoded=None
        for _ in range(struct.unpack_from('<I',saved,20)[0]):
            kind,_,blocks,chunkbytes=struct.unpack_from('<HHII',saved,pos)
            data=saved[pos+12:pos+chunkbytes]
            if kind != 0xcac3:
                assert cursor*block == start and blocks*block == len(raw) and decoded is None
                decoded=data if kind == 0xcac1 else data*(blocks*block//4)
            cursor+=blocks
            pos+=chunkbytes
        assert decoded == raw and cursor*block == size and pos == len(saved)
        digest.update(decoded)
        rows.append(dict(file=path.name,start=start,raw_bytes=len(raw),size=len(saved),sha256=hashlib.sha256(saved).hexdigest()))
assert digest.hexdigest() == report['sha256']
manifest=dict(format='android-sparse-contiguous-exact-v1',source_sha256=report['sha256'],expanded_size=size,
              all_decoded_spans_verified=True,zero_spans_written_as_fill=True,parts=rows)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(parts=len(rows),source_sha256=digest.hexdigest(),stored_bytes=sum(r['size'] for r in rows))))
