#!/usr/bin/env python3
"""Verify the boot-padding trace header, attribution token and content CRC."""
import argparse
import json
from pathlib import Path
import struct
import zlib


def main(raw,out,expected_token):
    b=raw.read_bytes();assert len(b)==4<<20
    magic,version,header_size,size,crc,flags,token=struct.unpack_from('<16sIIQII64s',b)
    assert magic.rstrip(b'\0')==b'C17_BOOTLOG_V1' and version==1 and header_size==4096
    token=token.split(b'\0')[0].decode()
    assert token==expected_token,(token,expected_token)
    assert 0<size<=len(b)-header_size
    payload=b[header_size:header_size+size]
    assert zlib.crc32(payload)==crc,'Reject incomplete or corrupted log data'
    out.mkdir(exist_ok=False)
    (out/'kmsg.raw').write_bytes(payload)
    (out/'kmsg.txt').write_text(payload.decode(errors='replace'))
    report=dict(state='ATTRIBUTED_BOOTLOG_CRC_PASS',token=token,bytes=size,producer_finished=bool(flags&1),
                raw=str(raw),boot_success=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--expected-token',required=True);a=ap.parse_args();main(a.raw,a.out_dir,a.expected_token)
