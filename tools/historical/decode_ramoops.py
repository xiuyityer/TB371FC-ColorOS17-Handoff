#!/usr/bin/env python3
"""Decode exact #789 no-ECC persistent RAM rings (Linux ram_core.c layout).

Input is the untouched 2 MiB reservation at 0x27e000000. No signature scanning
or guessed memory offsets. Raw ring bytes and validation metadata are retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def main(raw,out):
    data=raw.read_bytes()
    assert len(data)==2097152,'An exact 2 MiB read is required'
    out.mkdir(exist_ok=False)
    zones=[(f'dmesg-{i}',i*131072,131072) for i in range(8)]
    zones.append(('console',1048576,1048576))
    results=[]
    for name,offset,length in zones:
        sig,start,size=struct.unpack_from('<III',data,offset)
        row=dict(name=name,offset=offset,zone_bytes=length,signature=hex(sig),start=start,size=size)
        if sig!=0x43474244:
            row['state']='SIGNATURE_MISMATCH'
        elif size>length-12 or start>size:
            row['state']='INVALID_RING_BOUNDS'
        elif size==0:
            row['state']='VALID_EMPTY_RING'
        else:
            body=data[offset+12:offset+12+size]
            payload=body[start:]+body[:start]
            (out/(name+'.raw')).write_bytes(payload)
            row.update(state='VALID_RING_RECOVERED',sha256=hashlib.sha256(payload).hexdigest())
            text_payload=payload
            if name.startswith('dmesg-') and payload.startswith(b'===='):
                header,sep,body=payload.partition(b'\n')
                if header.endswith(b'-C') and sep:
                    try:
                        text_payload=header+b'\n'+zlib.decompress(body)
                        row['decompressed']=True
                    except zlib.error as e:
                        row['decompression_error']=str(e)
            (out/(name+'.txt')).write_text(text_payload.decode('utf-8',errors='replace'))
        results.append(row)
    report=dict(state='EXACT_LAYOUT_DECODE_COMPLETE_REQUIRES_BOOT_ATTRIBUTION',
                input=str(raw),sha256=hashlib.sha256(data).hexdigest(),physical_address='0x27e000000',
                kernel_source='smith-dog tag v2.2: fs/pstore/ram_core.c and ram.c',ecc_bytes=0,zones=results)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    a=ap.parse_args();main(a.raw,a.out_dir)
